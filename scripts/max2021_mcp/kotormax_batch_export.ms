-- Ghost Studio static-room bridge for KOTORMax v0.4.2.
--
-- 3dsmaxbatch loads the .MAX scene before this script. KOTORMax must be in
-- the active user scripts directory and autokotormax.ms must be in Startup so
-- its scripted classes are registered before the legacy NWMax scene opens.
-- KOTORMax preserves NWMax's permanent class IDs, allowing old AuroraBase,
-- AuroraTrimesh, and AuroraWalkmesh data to deserialize as Odyssey objects.
-- This script exports only; it never calls saveMaxFile.

global ExportOdysseyModel
global kx_exportmodelsilent
global kx_CreateExportName
global OdysseyBase
global g_exportPath
global g_exportwok
global g_dotAscii
global g_expLower
global g_ismax


fn ghostStudioCleanPath value =
(
    local result = if value == undefined then "" else value as string
    result = substituteString result "/" "\\"
    if result != "" and result[result.count] != "\\" do result += "\\"
    result
)


fn ghostStudioSafeText value =
(
    local result = if value == undefined then "" else value as string
    result = substituteString result "\t" " "
    result = substituteString result "\r" " "
    result = substituteString result "\n" " "
    result
)


fn ghostStudioCollectTree parent output =
(
    for child in parent.children do
    (
        append output child
        ghostStudioCollectTree child output
    )
    output
)


fn ghostStudioFileLength path =
(
    if not doesFileExist path then return 0
    ((dotNetObject "System.IO.FileInfo" path).Length as integer)
)


fn ghostStudioSnapshotFrozen parent =
(
    local nodes = #(parent)
    ghostStudioCollectTree parent nodes
    for node in nodes collect #(node, node.isFrozen)
)


fn ghostStudioRestoreFrozen states =
(
    for state in states where isValidNode state[1] do
    (
        if state[2] then freeze state[1] else unfreeze state[1]
    )
)


fn ghostStudioAllNodes =
(
    local nodes = #()
    ghostStudioCollectTree rootNode nodes
    nodes
)


fn ghostStudioNodesNamed nodeName =
(
    local matches = #()
    for node in ghostStudioAllNodes() where toLower(node.name) == toLower(nodeName) do
        append matches node
    matches
)


fn ghostStudioReadManifest manifestPath roomName =
(
    local names = #()
    local stream = undefined
    if not doesFileExist manifestPath then throw ("Missing sanity manifest: " + manifestPath)
    try
    (
        stream = openFile manifestPath mode:"r"
        while not eof stream do
        (
            local line = readLine stream
            local prefix = "Checking node "
            if line != undefined and findString line prefix == 1 then
            (
                local nodeName = substring line (prefix.count + 1) (line.count - prefix.count)
                if toLower(nodeName) != toLower(roomName) do append names nodeName
            )
        )
    )
    catch
    (
        if stream != undefined do close stream
        throw ("Cannot read sanity manifest " + manifestPath + ": " + (getCurrentException() as string))
    )
    if stream != undefined do close stream
    names
)


fn ghostStudioResolveManifest manifestPath roomName =
(
    local expectedNames = ghostStudioReadManifest manifestPath roomName
    local resolvedNodes = #()
    local missingNames = #()
    local uniqueNames = #()
    for nodeName in expectedNames where findItem uniqueNames nodeName == 0 do append uniqueNames nodeName
    for nodeName in uniqueNames do
    (
        local matches = ghostStudioNodesNamed nodeName
        local expectedCount = 0
        for expectedName in expectedNames where expectedName == nodeName do expectedCount += 1
        if matches.count != expectedCount then
            append missingNames (nodeName + " (expected " + (expectedCount as string) + ", found " + (matches.count as string) + ")")
        else for node in matches where findItem resolvedNodes node == 0 do append resolvedNodes node
    )
    #(expectedNames, resolvedNodes, missingNames)
)


fn ghostStudioExportBase modelBase outputDir report mode manifestNames:0 resolvedNodes:0 =
(
    -- kx_CreateExportName appends "-kotormax" for the stock UI. Recovery
    -- output must retain the exact room resref expected by LYT/MOD references.
    local exportName = toLower(modelBase.name)
    local mdlPath = outputDir + exportName + ".mdl.ascii"
    if doesFileExist mdlPath then throw ("Refusing to overwrite export: " + mdlPath)
    local stockExportName = toLower(kx_CreateExportName modelBase.name)
    local sidecarPaths = for extension in #(".wok.ascii", ".pwk.ascii", ".dwk.ascii") collect (outputDir + stockExportName + extension)
    for sidecarPath in sidecarPaths where doesFileExist sidecarPath do
        throw ("Refusing to overwrite KOTORMax sidecar: " + sidecarPath)

    local worldPosition = (in coordsys world at time 0 modelBase.pos) * 0.01
    local descendants = #()
    ghostStudioCollectTree modelBase descendants
    local frozenStates = ghostStudioSnapshotFrozen modelBase
    local priorExportPath = g_exportPath
    local priorBaseExportPath = if isProperty modelBase #export_path then modelBase.export_path else undefined
    local priorCopyTga = if isProperty modelBase #copy_tga then modelBase.copy_tga else undefined
    local priorTga2Dds = if isProperty modelBase #tga2dds then modelBase.tga2dds else undefined
    local exportError = undefined

    try
    (
        if priorBaseExportPath != undefined do modelBase.export_path = outputDir
        if priorCopyTga != undefined do modelBase.copy_tga = 0
        if priorTga2Dds != undefined do modelBase.tga2dds = 0
        g_exportPath = outputDir
        kx_exportmodelsilent modelBase mdlPath false
    )
    catch
    (
        exportError = getCurrentException() as string
    )

    g_exportPath = priorExportPath
    if priorBaseExportPath != undefined do modelBase.export_path = priorBaseExportPath
    if priorCopyTga != undefined do modelBase.copy_tga = priorCopyTga
    if priorTga2Dds != undefined do modelBase.tga2dds = priorTga2Dds
    ghostStudioRestoreFrozen frozenStates

    if exportError != undefined then
    (
        if doesFileExist mdlPath do deleteFile mdlPath
        for sidecarPath in sidecarPaths where doesFileExist sidecarPath do deleteFile sidecarPath
        throw ("KOTORMax export failed for " + modelBase.name + ": " + exportError)
    )
    if not doesFileExist mdlPath then throw ("KOTORMax produced no ASCII MDL: " + mdlPath)
    if ghostStudioFileLength mdlPath == 0 then
    (
        deleteFile mdlPath
        throw ("KOTORMax produced an empty ASCII MDL: " + mdlPath)
    )

    format "%\t%\t%\t%\t%\t%\t%\t%\t%\t%\n" \
        (ghostStudioSafeText maxFileName) \
        (ghostStudioSafeText modelBase.name) \
        mode worldPosition.x worldPosition.y worldPosition.z descendants.count \
        manifestNames resolvedNodes \
        (ghostStudioSafeText mdlPath) to:report
    flush report
    true
)


fn ghostStudioExportReconstructed roomName manifestPath outputDir report =
(
    if ghostStudioNodesNamed(roomName).count > 0 then
        throw (roomName + " already exists; refusing temporary duplicate root.")

    local resolved = ghostStudioResolveManifest manifestPath roomName
    local expectedNames = resolved[1]
    local nodes = resolved[2]
    local missingNames = resolved[3]
    if missingNames.count > 0 then
        throw (roomName + " is missing manifest nodes: " + (missingNames as string))
    if nodes.count == 0 then throw (roomName + " resolved no scene nodes.")

    local base = undefined
    local changedParents = #()
    local exported = false
    local errorText = undefined
    try
    (
        base = OdysseyBase name:roomName
        if isProperty base #classification do base.classification = "other"
        if isProperty base #setsupermodel do base.setsupermodel = "NULL"
        if isProperty base #export_path do base.export_path = outputDir
        if isProperty base #uselyt do base.uselyt = 1

        -- Preserve internal hierarchy. Only target nodes whose parent is not
        -- another target node are temporarily attached to the new root. Save
        -- and restore the world matrix explicitly so reparenting cannot move
        -- the recovered geometry.
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
        exported = ghostStudioExportBase base outputDir report "reconstructed" \
            manifestNames:expectedNames.count resolvedNodes:nodes.count
    )
    catch
    (
        errorText = getCurrentException() as string
    )

    for index = changedParents.count to 1 by -1 do
    (
        local record = changedParents[index]
        if isValidNode record[1] do
        (
            with animate off
            (
                record[1].parent = record[2]
                at time 0 record[1].transform = record[3]
            )
        )
    )
    if base != undefined and isValidNode base do delete base
    if errorText != undefined then throw errorText
    exported
)


local outputDir = ghostStudioCleanPath(getEnvVariable "GHOSTSTUDIO_KOTOR_EXPORT_DIR")
local rootPattern = getEnvVariable "GHOSTSTUDIO_KOTOR_ROOT_PATTERN"
local sanityDir = ghostStudioCleanPath(getEnvVariable "GHOSTSTUDIO_KOTOR_SANITY_DIR")
local reconstructSpec = getEnvVariable "GHOSTSTUDIO_KOTOR_RECONSTRUCT_ROOMS"
if rootPattern == undefined or rootPattern == "" do rootPattern = "vul803_01?"
if reconstructSpec == undefined do reconstructSpec = ""
if outputDir == "" then throw "GHOSTSTUDIO_KOTOR_EXPORT_DIR is not set."
if ExportOdysseyModel == undefined or kx_exportmodelsilent == undefined or OdysseyBase == undefined then
    throw "KOTORMax is not loaded. Install KOTORMax v0.4.2 before the scene is opened."
if g_ismax != true then throw "KOTORMax did not initialize in 3ds Max mode."

local directoryClass = dotNetClass "System.IO.Directory"
if not directoryClass.Exists outputDir do directoryClass.CreateDirectory outputDir
local reportPath = outputDir + "ghoststudio-kotormax-export.tsv"
if doesFileExist reportPath then throw ("Refusing to overwrite report: " + reportPath)
local report = createFile reportPath
if report == undefined then throw ("Cannot create export report: " + reportPath)
local exportCount = 0
local batchError = undefined
local priorExportPath = g_exportPath
local priorExportWok = g_exportwok
local priorDotAscii = g_dotAscii
local priorExpLower = g_expLower

try
(
    format "scene\troot\tmode\tposition_x\tposition_y\tposition_z\tdescendants\tmanifest_names\tresolved_nodes\tmdl_ascii\n" to:report
    g_exportPath = outputDir
    -- Sidecar WOK export is deliberately disabled. The embedded AABB remains
    -- in the ASCII MDL; Ghost Studio derives/proves the floor-only WOK later.
    g_exportwok = 0
    g_dotAscii = 1
    g_expLower = 1

    local existingRoots = for helper in helpers where
    (
        iskindof helper OdysseyBase and matchPattern (toLower helper.name) pattern:(toLower rootPattern)
    ) collect helper
    for modelBase in existingRoots do
    (
        if ghostStudioExportBase modelBase outputDir report "saved_root" do exportCount += 1
    )

    local reconstructRooms = if reconstructSpec == "" then #() else filterString reconstructSpec ";"
    for roomName in reconstructRooms do
    (
        if sanityDir == "" then throw "GHOSTSTUDIO_KOTOR_SANITY_DIR is required for root reconstruction."
        local manifestPath = sanityDir + roomName + "_sanitycheck.txt"
        if ghostStudioExportReconstructed roomName manifestPath outputDir report do exportCount += 1
    )
    if exportCount == 0 then throw ("No KOTORMax OdysseyBase matched " + rootPattern + " in " + maxFileName)
)
catch
(
    batchError = getCurrentException() as string
)

flush report
close report
g_exportPath = priorExportPath
g_exportwok = priorExportWok
g_dotAscii = priorDotAscii
g_expLower = priorExpLower
if batchError != undefined then throw batchError
format "Ghost Studio KOTORMax export complete: % room root(s) -> %\n" exportCount outputDir
