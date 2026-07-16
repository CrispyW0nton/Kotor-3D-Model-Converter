-- Ghost Studio - vul803 legacy NWMax 0.8 b60 recovery bridge
--
-- This is the preferred first-stage exporter for the original Max 9 scenes.
-- It deliberately does not open, save, or overwrite a .max scene.  Install
-- and load the preserved NWMax 0.8 b60 tree in an isolated 3ds Max process,
-- open a COPY of the source scene, and then call a function documented in the
-- README beside this file.
--
-- Never load KOTORMax in the same 3ds Max process.  NWMax and KOTORMax reuse
-- permanent scripted-plugin class IDs and global names, but not every saved
-- class has the same superclass (notably AuroraDLight).

global ExAuroraMDL
global SanityCheck
global nx_strclassof
global AuroraBase
global AuroraTrimesh
global AuroraFlex
global AuroraWalkmesh
global AuroraLight
global AuroraDLight
global AuroraEmitter
global AuroraReference
global g_strBuffer
global g_exportPath
global gblVersion
global g_ismax


fn ghostVul803NwmaxLog message =
(
    format "[Ghost Studio vul803/NWMax] %\n" message
)


fn ghostVul803NwmaxCombinePath parent child =
(
    (dotNetClass "System.IO.Path").Combine parent child
)


fn ghostVul803NwmaxDirectoryExists path =
(
    (dotNetClass "System.IO.Directory").Exists path
)


fn ghostVul803NwmaxFileExists path =
(
    (dotNetClass "System.IO.File").Exists path
)


fn ghostVul803NwmaxFileLength path =
(
    if not ghostVul803NwmaxFileExists path then return 0
    ((dotNetObject "System.IO.FileInfo" path).Length as integer)
)


fn ghostVul803NwmaxWithTrailingSlash path =
(
    if path.count == 0 then return path
    local lastCharacter = path[path.count]
    if lastCharacter != "\\" and lastCharacter != "/" then path + "\\" else path
)


fn ghostVul803NwmaxCollectTree parent output =
(
    for child in parent.children do
    (
        append output child
        ghostVul803NwmaxCollectTree child output
    )
    output
)


fn ghostVul803NwmaxSnapshotFrozen parent =
(
    local nodes = #(parent)
    ghostVul803NwmaxCollectTree parent nodes
    for node in nodes collect #(node, node.isFrozen)
)


fn ghostVul803NwmaxRestoreFrozen states =
(
    for state in states where isValidNode state[1] do
    (
        if state[2] then freeze state[1] else unfreeze state[1]
    )
)


fn ghostVul803NwmaxAllNodes =
(
    local nodes = #()
    ghostVul803NwmaxCollectTree rootNode nodes
    nodes
)


fn ghostVul803NwmaxNodesNamed nodeName =
(
    local matches = #()
    local sceneNodes = ghostVul803NwmaxAllNodes()
    for node in sceneNodes where node.name == nodeName do append matches node
    matches
)


fn ghostVul803NwmaxReadSanityManifest sanityReport roomName =
(
    local names = #()
    local stream = undefined

    if not ghostVul803NwmaxFileExists sanityReport then
    (
        ghostVul803NwmaxLog ("Missing sanity report: " + sanityReport)
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
                -- Preserve duplicate occurrences. The sanity report records
                -- one row per scene node, so multiplicity is part of the
                -- recovered room-membership contract.
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


fn ghostVul803NwmaxResolveManifest sanityReport roomName =
(
    local expectedNames = ghostVul803NwmaxReadSanityManifest sanityReport roomName
    local resolvedNodes = #()
    local missingNames = #()
    local uniqueNames = #()

    for nodeName in expectedNames where findItem uniqueNames nodeName == 0 do append uniqueNames nodeName
    for nodeName in uniqueNames do
    (
        local matches = ghostVul803NwmaxNodesNamed nodeName
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


fn ghostVul803NwmaxRequireLegacyNwmax =
(
    if ExAuroraMDL == undefined or SanityCheck == undefined or \
       nx_strclassof == undefined or AuroraBase == undefined or \
       AuroraTrimesh == undefined or AuroraFlex == undefined or \
       AuroraWalkmesh == undefined or AuroraLight == undefined or \
       AuroraDLight == undefined or AuroraEmitter == undefined or \
       AuroraReference == undefined then
    (
        ghostVul803NwmaxLog "NWMax is not fully loaded. Load the preserved NWMax 0.8 b60 tree before opening the source scene."
        return false
    )

    if g_ismax != true then
    (
        ghostVul803NwmaxLog "NWMax is configured for gmax. Set [init] usemax=1 in NWmax.ini and restart 3ds Max."
        return false
    )

    if gblVersion != "0.8 b60" then
    (
        ghostVul803NwmaxLog ("Refusing an unaudited NWMax version: " + (gblVersion as string))
        return false
    )

    ghostVul803NwmaxLog "Legacy NWMax 0.8 b60 detected in 3ds Max mode."
    true
)


fn ghostVul803NwmaxAuditManifest sanityReport roomName =
(
    local result = ghostVul803NwmaxResolveManifest sanityReport roomName
    local expectedNames = result[1]
    local resolvedNodes = result[2]
    local missingNames = result[3]

    ghostVul803NwmaxLog (roomName + " manifest names: " + (expectedNames.count as string))
    ghostVul803NwmaxLog (roomName + " resolved scene nodes: " + (resolvedNodes.count as string))

    if missingNames.count > 0 then
    (
        ghostVul803NwmaxLog (roomName + " missing names: " + (missingNames as string))
        return false
    )

    true
)


fn ghostVul803NwmaxOutputPathsAreClear roomName outputDirectory =
(
    -- ExAuroraMDL can emit these sidecars depending on the saved base and
    -- child types.  Preflight all of them so legacy export cannot overwrite a
    -- file even when the scene contains an unexpected Tile/PWK/DWK setup.
    local candidates = #(
        roomName + ".mdl.ascii",
        roomName + ".wok",
        roomName + ".pwk",
        roomName + ".dwk"
    )

    for candidate in candidates do
    (
        local path = ghostVul803NwmaxCombinePath outputDirectory candidate
        if ghostVul803NwmaxFileExists path then
        (
            ghostVul803NwmaxLog ("Refusing to overwrite output or sidecar: " + path)
            return false
        )
    )

    true
)


fn ghostVul803NwmaxRunSanity base reportPath =
(
    local priorBuffer = g_strBuffer
    local report = undefined
    local result = 0
    local errorText = undefined

    if ghostVul803NwmaxFileExists reportPath then
    (
        ghostVul803NwmaxLog ("Refusing to overwrite sanity report: " + reportPath)
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
        ghostVul803NwmaxLog ("NWMax sanity check failed: " + errorText)
        return #error
    )

    if result != 1 then
    (
        ghostVul803NwmaxLog ("NWMax sanity check rejected the room; inspect " + reportPath)
        return #fail
    )

    #pass
)


fn ghostVul803NwmaxWriteBase base outputDirectory =
(
    local roomName = base.name
    local outputPath = ghostVul803NwmaxCombinePath outputDirectory (roomName + ".mdl.ascii")
    local priorBuffer = g_strBuffer
    local priorExportPath = g_exportPath
    local priorSliderTime = sliderTime
    local frozenStates = ghostVul803NwmaxSnapshotFrozen base
    local output = undefined
    local errorText = undefined

    try
    (
        g_exportPath = ghostVul803NwmaxWithTrailingSlash outputDirectory
        output = createFile outputPath
        if output == undefined then throw ("Cannot create ASCII export: " + outputPath)
        g_strBuffer = output
        ExAuroraMDL base anim:false
    )
    catch
    (
        errorText = getCurrentException() as string
    )

    if output != undefined do
    (
        flush output
        close output
    )
    g_strBuffer = priorBuffer
    g_exportPath = priorExportPath
    sliderTime = priorSliderTime
    ghostVul803NwmaxRestoreFrozen frozenStates

    if errorText != undefined then
    (
        if ghostVul803NwmaxFileExists outputPath do deleteFile outputPath
        ghostVul803NwmaxLog ("NWMax export failed: " + errorText)
        return false
    )

    if ghostVul803NwmaxFileLength outputPath == 0 then
    (
        if ghostVul803NwmaxFileExists outputPath do deleteFile outputPath
        ghostVul803NwmaxLog ("NWMax produced an empty export: " + outputPath)
        return false
    )

    ghostVul803NwmaxLog ("Exported legacy ASCII non-destructively: " + outputPath)
    true
)


fn ghostVul803NwmaxExportBase base outputDirectory allowSanityFailure:false =
(
    local roomName = base.name
    local sanityPath = ghostVul803NwmaxCombinePath outputDirectory (roomName + "_sanitycheck.txt")

    if not ghostVul803NwmaxRequireLegacyNwmax() then return false
    if not ghostVul803NwmaxDirectoryExists outputDirectory then
    (
        ghostVul803NwmaxLog ("Output directory does not exist: " + outputDirectory)
        return false
    )
    if not ghostVul803NwmaxOutputPathsAreClear roomName outputDirectory then return false
    if nx_strclassof base != "aurorabase" then
    (
        ghostVul803NwmaxLog (roomName + " is not a legacy AuroraBase.")
        return false
    )
    if base.children.count == 0 then
    (
        ghostVul803NwmaxLog (roomName + " has no children.")
        return false
    )

    local sanityResult = ghostVul803NwmaxRunSanity base sanityPath
    if sanityResult == #error then return false
    if sanityResult == #fail and not allowSanityFailure then return false
    if sanityResult == #fail do
    (
        ghostVul803NwmaxLog "Explicit override accepted the failed sanity check. This ASCII is recovery input, not an engine-ready model."
    )

    ghostVul803NwmaxWriteBase base outputDirectory
)


fn ghostVul803NwmaxExportExistingRoot roomName outputDirectory allowSanityFailure:false =
(
    local roots = ghostVul803NwmaxNodesNamed roomName
    if roots.count != 1 then
    (
        ghostVul803NwmaxLog ("Expected exactly one " + roomName + " root; found " + (roots.count as string))
        return false
    )

    local base = roots[1]
    local priorExportPath = if isProperty base #export_path then base.export_path else undefined
    local result = false

    if isProperty base #export_path do base.export_path = outputDirectory
    result = ghostVul803NwmaxExportBase base outputDirectory allowSanityFailure:allowSanityFailure
    if priorExportPath != undefined do base.export_path = priorExportPath
    result
)


fn ghostVul803NwmaxExportManifest roomName sanityReport outputDirectory allowSanityFailure:false replaceExistingRoot:false =
(
    if not ghostVul803NwmaxRequireLegacyNwmax() then return false

    local existingRoots = ghostVul803NwmaxNodesNamed roomName
    if existingRoots.count > 1 then
    (
        ghostVul803NwmaxLog ("Expected no more than one existing " + roomName + " root; found " + (existingRoots.count as string))
        return false
    )
    if existingRoots.count == 1 and not replaceExistingRoot then
    (
        ghostVul803NwmaxLog (roomName + " already exists. Use replaceExistingRoot:true to export the historical manifest partition, or use ghostVul803NwmaxExportExistingRoot for a forensic whole-root export.")
        return false
    )

    local resolved = ghostVul803NwmaxResolveManifest sanityReport roomName
    local nodes = resolved[2]
    local missingNames = resolved[3]
    if missingNames.count > 0 then
    (
        ghostVul803NwmaxLog (roomName + " is missing manifest nodes: " + (missingNames as string))
        return false
    )
    if nodes.count == 0 then
    (
        ghostVul803NwmaxLog (roomName + " resolved no scene nodes.")
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
            if (ghostVul803NwmaxNodesNamed hiddenRootName).count > 0 then
                throw ("Temporary root name already exists: " + hiddenRootName)
            savedRoot.name = hiddenRootName
            if savedRoot.name != hiddenRootName then
                throw ("Could not temporarily rename saved root: " + roomName)
        )

        base = AuroraBase name:roomName
        if base.name != roomName then throw ("Could not create exact temporary root name: " + roomName)
        if isProperty base #classification do base.classification = "Other"
        if isProperty base #setsupermodel do base.setsupermodel = "NULL"
        if isProperty base #export_path do base.export_path = outputDirectory
        if isProperty base #export_binary do base.export_binary = 0
        if isProperty base #sanity_check do base.sanity_check = 1
        if isProperty base #copy_tga do base.copy_tga = 0
        if isProperty base #tga2dds do base.tga2dds = 0

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

        exportResult = ghostVul803NwmaxExportBase base outputDirectory allowSanityFailure:allowSanityFailure
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
        ghostVul803NwmaxLog ("Temporary room export failed: " + errorText)
        return false
    )

    exportResult
)


ghostVul803NwmaxLog "Legacy bridge loaded. No scene was opened, saved, or changed."
