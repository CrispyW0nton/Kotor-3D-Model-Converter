-- Ghost Studio - vul803 KOTORMax geometry-recovery bridge
--
-- This script deliberately does not open, save, or overwrite a .max scene.
-- Open a COPY of the source scene manually after KOTORMax has loaded, then
-- call one of the functions documented in README.md beside this file.
--
-- The bridge supports the latest OpenKotOR KOTORMax scripts.  Prefer the
-- legacy NWMax bridge for the first export of original .max scenes: the saved
-- AuroraDLight helper has no lossless KOTORMax class replacement.  KOTORMax and
-- NWMax must never be loaded in the same 3ds Max process because both define
-- the same permanent scripted-plugin class IDs and global names.

global ExportOdysseyModel
global SanityCheck
global kx_exportmodelsilent
global kx_CreateExportName
global kx_strclassof
global OdysseyBase
global OdysseyTrimesh
global OdysseyFlex
global OdysseyWalkmesh
global OdysseyLight
global OdysseyEmitter
global OdysseyReference
global g_strBuffer
global g_exportPath
global g_exportwok
global g_dotAscii
global gblVersion
global g_ismax


fn ghostVul803Log message =
(
    format "[Ghost Studio vul803] %\n" message
)


fn ghostVul803FullPath path =
(
    try
    (
        return (dotNetClass "System.IO.Path").GetFullPath path
    )
    catch
    (
        return path
    )
)


fn ghostVul803CombinePath parent child =
(
    (dotNetClass "System.IO.Path").Combine parent child
)


fn ghostVul803DirectoryExists path =
(
    (dotNetClass "System.IO.Directory").Exists path
)


fn ghostVul803WithTrailingSlash path =
(
    if path.count == 0 then return path
    local lastCharacter = path[path.count]
    if lastCharacter != "\\" and lastCharacter != "/" then path + "\\" else path
)


fn ghostVul803FileExists path =
(
    (dotNetClass "System.IO.File").Exists path
)


fn ghostVul803FileLength path =
(
    if not ghostVul803FileExists path then return 0
    ((dotNetObject "System.IO.FileInfo" path).Length as integer)
)


fn ghostVul803CollectTree parent output =
(
    for child in parent.children do
    (
        append output child
        ghostVul803CollectTree child output
    )
    output
)


fn ghostVul803SnapshotFrozen parent =
(
    local nodes = #(parent)
    ghostVul803CollectTree parent nodes
    for node in nodes collect #(node, node.isFrozen)
)


fn ghostVul803RestoreFrozen states =
(
    for state in states where isValidNode state[1] do
    (
        if state[2] then freeze state[1] else unfreeze state[1]
    )
)


fn ghostVul803AllNodes =
(
    local nodes = #()
    ghostVul803CollectTree rootNode nodes
    nodes
)


fn ghostVul803NodesNamed nodeName =
(
    local matches = #()
    local sceneNodes = ghostVul803AllNodes()
    for node in sceneNodes where node.name == nodeName do
    (
        append matches node
    )
    matches
)


fn ghostVul803ReadSanityManifest sanityReport roomName =
(
    local names = #()
    local stream = undefined

    if not ghostVul803FileExists sanityReport then
    (
        ghostVul803Log ("Missing sanity report: " + sanityReport)
        return names
    )

    try
    (
        stream = openFile sanityReport mode:"r"
        while not eof stream do
        (
            local line = readLine stream
            local prefix = "Checking node "
            if line != undefined and matchPattern line pattern:(prefix + "*") then
            (
                local nodeName = substring line (prefix.count + 1) (line.count - prefix.count)
                -- Preserve duplicate occurrences; each sanity row represents
                -- one scene node in the historical room membership.
                if nodeName != roomName do append names nodeName
            )
        )
    )
    catch
    (
        if stream != undefined do close stream
        throw ("Failed to read sanity report " + sanityReport + ": " + (getCurrentException() as string))
    )

    if stream != undefined do close stream
    names
)


fn ghostVul803ResolveManifest sanityReport roomName =
(
    local expectedNames = ghostVul803ReadSanityManifest sanityReport roomName
    local resolvedNodes = #()
    local missingNames = #()
    local uniqueNames = #()

    for nodeName in expectedNames where findItem uniqueNames nodeName == 0 do append uniqueNames nodeName
    for nodeName in uniqueNames do
    (
        local matches = ghostVul803NodesNamed nodeName
        local expectedCount = 0
        for expectedName in expectedNames where expectedName == nodeName do expectedCount += 1
        if matches.count != expectedCount then
        (
            append missingNames (nodeName + " (expected " + (expectedCount as string) + ", found " + (matches.count as string) + ")")
        )
        else
        (
            for node in matches where findItem resolvedNodes node == 0 do append resolvedNodes node
        )
    )

    #(expectedNames, resolvedNodes, missingNames)
)


fn ghostVul803RequireKotorMax =
(
    if ExportOdysseyModel == undefined or kx_exportmodelsilent == undefined or \
       SanityCheck == undefined or kx_strclassof == undefined or \
       OdysseyBase == undefined or OdysseyTrimesh == undefined or \
       OdysseyFlex == undefined or OdysseyWalkmesh == undefined or \
       OdysseyLight == undefined or OdysseyEmitter == undefined or \
       OdysseyReference == undefined then
    (
        ghostVul803Log "KOTORMax is not fully loaded. Load KOTORMax before opening the source scene."
        return false
    )

    if g_ismax != true then
    (
        ghostVul803Log "This bridge requires Autodesk 3ds Max, not gmax."
        return false
    )

    ghostVul803Log ("KOTORMax detected: " + (gblVersion as string))
    true
)


fn ghostVul803AuditManifest sanityReport roomName =
(
    local result = ghostVul803ResolveManifest sanityReport roomName
    local expectedNames = result[1]
    local resolvedNodes = result[2]
    local missingNames = result[3]

    ghostVul803Log (roomName + " manifest names: " + (expectedNames.count as string))
    ghostVul803Log (roomName + " resolved scene nodes: " + (resolvedNodes.count as string))

    if missingNames.count > 0 then
    (
        ghostVul803Log (roomName + " missing names: " + (missingNames as string))
        return false
    )

    true
)


fn ghostVul803RunSanity base reportPath =
(
    local priorBuffer = g_strBuffer
    local report = undefined
    local result = 0
    local errorText = undefined

    if ghostVul803FileExists reportPath then
    (
        ghostVul803Log ("Refusing to overwrite sanity report: " + reportPath)
        return #error
    )

    try
    (
        report = createFile reportPath
        if report == undefined then throw ("Cannot create sanity report: " + reportPath)
        g_strBuffer = report
        result = SanityCheck base
    )
    catch
    (
        errorText = getCurrentException() as string
    )

    if report != undefined do
    (
        flush report
        close report
    )
    g_strBuffer = priorBuffer

    if errorText != undefined then
    (
        ghostVul803Log ("KOTORMax sanity check failed: " + errorText)
        return #error
    )

    if result != 1 then
    (
        ghostVul803Log ("KOTORMax sanity check rejected the room; inspect " + reportPath)
        return #fail
    )

    #pass
)


fn ghostVul803ExportBase base outputDirectory allowSanityFailure:false =
(
    local roomName = base.name
    local outputPath = ghostVul803CombinePath outputDirectory (roomName + ".mdl.ascii")
    local sanityPath = ghostVul803CombinePath outputDirectory (roomName + "_sanitycheck.txt")

    if not ghostVul803RequireKotorMax() then return false
    if not ghostVul803DirectoryExists outputDirectory then
    (
        ghostVul803Log ("Output directory does not exist: " + outputDirectory)
        return false
    )
    if ghostVul803FileExists outputPath then
    (
        ghostVul803Log ("Refusing to overwrite export: " + outputPath)
        return false
    )
    local stockExportName = toLower(kx_CreateExportName roomName)
    for sidecarName in #(
        roomName + ".wok", roomName + ".wok.ascii",
        roomName + ".pwk", roomName + ".pwk.ascii",
        roomName + ".dwk", roomName + ".dwk.ascii",
        stockExportName + ".wok", stockExportName + ".wok.ascii",
        stockExportName + ".pwk", stockExportName + ".pwk.ascii",
        stockExportName + ".dwk", stockExportName + ".dwk.ascii") do
    (
        local sidecarPath = ghostVul803CombinePath outputDirectory sidecarName
        if ghostVul803FileExists sidecarPath then
        (
            ghostVul803Log ("Refusing to overwrite output sidecar: " + sidecarPath)
            return false
        )
    )
    if kx_strclassof base != "odysseybase" then
    (
        ghostVul803Log (roomName + " is not an OdysseyBase after KOTORMax migration.")
        return false
    )
    if base.children.count == 0 then
    (
        ghostVul803Log (roomName + " has no children.")
        return false
    )
    local sanityResult = ghostVul803RunSanity base sanityPath
    if sanityResult == #error then return false
    if sanityResult == #fail and not allowSanityFailure then return false
    if sanityResult == #fail do
    (
        ghostVul803Log "Explicit override accepted the failed sanity check. This ASCII is recovery input, not an engine-ready model."
    )

    local priorGlobalExportPath = g_exportPath
    local priorExportWok = g_exportwok
    local priorDotAscii = g_dotAscii
    local priorCopyTga = if isProperty base #copy_tga then base.copy_tga else undefined
    local priorTga2Dds = if isProperty base #tga2dds then base.tga2dds else undefined
    local frozenStates = ghostVul803SnapshotFrozen base
    local exportError = undefined

    -- kx_exportmodelsilent consumes exporter globals rather than only the
    -- explicit filename.  Point them at the guarded output directory and
    -- suppress generated WOK/TGA sidecars: this bridge recovers geometry;
    -- walkmesh generation and proof happen downstream in Ghost Studio.
    g_exportPath = ghostVul803WithTrailingSlash outputDirectory
    g_exportwok = 0
    g_dotAscii = 1
    if priorCopyTga != undefined do base.copy_tga = 0
    if priorTga2Dds != undefined do base.tga2dds = 0

    try
    (
        kx_exportmodelsilent base outputPath false
    )
    catch
    (
        exportError = getCurrentException() as string
    )

    g_exportPath = priorGlobalExportPath
    g_exportwok = priorExportWok
    g_dotAscii = priorDotAscii
    if priorCopyTga != undefined do base.copy_tga = priorCopyTga
    if priorTga2Dds != undefined do base.tga2dds = priorTga2Dds
    ghostVul803RestoreFrozen frozenStates

    if exportError != undefined then
    (
        if ghostVul803FileExists outputPath do deleteFile outputPath
        ghostVul803Log ("KOTORMax export failed: " + exportError)
        return false
    )

    if not ghostVul803FileExists outputPath then
    (
        ghostVul803Log ("KOTORMax returned without producing: " + outputPath)
        return false
    )
    if ghostVul803FileLength outputPath == 0 then
    (
        deleteFile outputPath
        ghostVul803Log ("KOTORMax produced an empty export: " + outputPath)
        return false
    )

    ghostVul803Log ("Exported non-destructively: " + outputPath)
    true
)


fn ghostVul803ExportExistingRoot roomName outputDirectory allowSanityFailure:false =
(
    local roots = ghostVul803NodesNamed roomName
    if roots.count != 1 then
    (
        ghostVul803Log ("Expected exactly one " + roomName + " root; found " + (roots.count as string))
        return false
    )

    local base = roots[1]
    local priorExportPath = if isProperty base #export_path then base.export_path else undefined
    local result = false

    if isProperty base #export_path do base.export_path = outputDirectory
    result = ghostVul803ExportBase base outputDirectory allowSanityFailure:allowSanityFailure
    if priorExportPath != undefined do base.export_path = priorExportPath
    result
)


fn ghostVul803ExportManifest roomName sanityReport outputDirectory allowSanityFailure:false replaceExistingRoot:false =
(
    if not ghostVul803RequireKotorMax() then return false

    local existingRoots = ghostVul803NodesNamed roomName
    if existingRoots.count > 1 then
    (
        ghostVul803Log ("Expected no more than one existing " + roomName + " root; found " + (existingRoots.count as string))
        return false
    )
    if existingRoots.count == 1 and not replaceExistingRoot then
    (
        ghostVul803Log (roomName + " already exists. Use replaceExistingRoot:true to export the historical manifest partition, or use ghostVul803ExportExistingRoot for a forensic whole-root export.")
        return false
    )

    local resolved = ghostVul803ResolveManifest sanityReport roomName
    local nodes = resolved[2]
    local missingNames = resolved[3]
    if missingNames.count > 0 then
    (
        ghostVul803Log (roomName + " is missing manifest nodes: " + (missingNames as string))
        return false
    )
    if nodes.count == 0 then
    (
        ghostVul803Log (roomName + " resolved no scene nodes.")
        return false
    )

    local base = undefined
    local savedRoot = if existingRoots.count == 1 then existingRoots[1] else undefined
    local savedRootName = if savedRoot != undefined then savedRoot.name else undefined
    local hiddenRootName = "__GhostSaved_" + roomName
    local changedParents = #()
    local exportResult = false
    local errorText = undefined

    try
    (
        if savedRoot != undefined then
        (
            if (ghostVul803NodesNamed hiddenRootName).count > 0 then
                throw ("Temporary root name already exists: " + hiddenRootName)
            savedRoot.name = hiddenRootName
            if savedRoot.name != hiddenRootName then
                throw ("Could not temporarily rename saved root: " + roomName)
        )

        base = OdysseyBase name:roomName
        if base.name != roomName then throw ("Could not create exact temporary root name: " + roomName)
        if isProperty base #classification do base.classification = "other"
        if isProperty base #setsupermodel do base.setsupermodel = "NULL"
        if isProperty base #export_path do base.export_path = outputDirectory
        if isProperty base #sanity_check do base.sanity_check = 1
        if isProperty base #uselyt do base.uselyt = 1

        -- Preserve every internal hierarchy.  Only manifest nodes whose parent
        -- is outside the manifest are temporarily attached to the new base.
        for node in nodes do
        (
            if node.parent == undefined or findItem nodes node.parent == 0 then
            (
                if isAnimated node.transform.controller then
                    throw ("Refusing to reparent animated top-level manifest node: " + node.name)
                local worldTM = copy (at time 0 node.transform)
                append changedParents #(node, node.parent, worldTM)
                with animate off
                (
                    node.parent = base
                    at time 0 node.transform = worldTM
                )
            )
        )

        exportResult = ghostVul803ExportBase base outputDirectory allowSanityFailure:allowSanityFailure
    )
    catch
    (
        errorText = getCurrentException() as string
    )

    -- Always restore the open scene.  The script never calls saveMaxFile.
    for recordIndex = changedParents.count to 1 by -1 do
    (
        local parentRecord = changedParents[recordIndex]
        if isValidNode parentRecord[1] do
        (
            with animate off
            (
                parentRecord[1].parent = parentRecord[2]
                at time 0 parentRecord[1].transform = parentRecord[3]
            )
        )
    )
    if base != undefined and isValidNode base do delete base
    if savedRoot != undefined and isValidNode savedRoot do savedRoot.name = savedRootName

    if errorText != undefined then
    (
        ghostVul803Log ("Temporary room export failed: " + errorText)
        return false
    )

    exportResult
)


ghostVul803Log "Bridge loaded. No scene was opened, saved, or changed."
