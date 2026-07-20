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
    pathConfig.appendPath parent child
)


fn ghostVul803NwmaxDirectoryExists path =
(
    doesDirectoryExist path
)


fn ghostVul803NwmaxFileExists path =
(
    doesFileExist path
)


fn ghostVul803NwmaxFileLength path =
(
    if not ghostVul803NwmaxFileExists path then return 0
    getFileSize path
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


fn ghostVul803NwmaxControllerIsProvenStatic controller visited =
(
    if controller == undefined then return true
    if findItem visited controller != 0 then return true
    append visited controller

    local className = toLower ((classOf controller) as string)
    local keyControllerClasses = #(
        "bezier_float", "linear_float", "tcb_float",
        "bezier_position", "linear_position", "tcb_position",
        "bezier_rotation", "linear_rotation", "tcb_rotation", "smooth_rotation",
        "bezier_scale", "linear_scale", "tcb_scale"
    )
    local compoundControllerClasses = #("position_xyz", "euler_xyz", "local_euler_xyz", "scalexyz")

    if findItem keyControllerClasses className != 0 then
    (
        local supports = undefined
        local keyCount = undefined
        try (supports = controller.supportsKeys) catch ()
        if supports != true then return false
        try (keyCount = numKeys controller) catch ()
        return keyCount == 0
    )

    if findItem compoundControllerClasses className == 0 then return false
    local xyzControllers = undefined
    try (xyzControllers = getXYZControllers controller) catch ()
    if xyzControllers == undefined or xyzControllers.count != 3 then return false
    for subController in xyzControllers do
    (
        if subController == undefined or \
           not ghostVul803NwmaxControllerIsProvenStatic subController visited then return false
    )
    true
)


fn ghostVul803NwmaxTransformHasKeys node =
(
    if node == undefined then return true
    local controllers = #(node.position.controller, node.rotation.controller, node.scale.controller)
    local visited = #()
    for controller in controllers where not ghostVul803NwmaxControllerIsProvenStatic controller visited do return true
    false
)


fn ghostVul803NwmaxPointNear left right tolerance =
(
    abs (left.x - right.x) <= tolerance and \
    abs (left.y - right.y) <= tolerance and \
    abs (left.z - right.z) <= tolerance
)


fn ghostVul803NwmaxUnitScale scaleValue tolerance:0.0001 =
(
    ghostVul803NwmaxPointNear scaleValue [1.0, 1.0, 1.0] tolerance
)


fn ghostVul803NwmaxScalarNearRelative left right absoluteTolerance relativeTolerance =
(
    local magnitude = abs left
    if abs right > magnitude do magnitude = abs right
    local allowed = absoluteTolerance
    if magnitude * relativeTolerance > allowed do allowed = magnitude * relativeTolerance
    abs (left - right) <= allowed
)


fn ghostVul803NwmaxPointNearRelative left right absoluteTolerance relativeTolerance =
(
    ghostVul803NwmaxScalarNearRelative left.x right.x absoluteTolerance relativeTolerance and \
    ghostVul803NwmaxScalarNearRelative left.y right.y absoluteTolerance relativeTolerance and \
    ghostVul803NwmaxScalarNearRelative left.z right.z absoluteTolerance relativeTolerance
)


fn ghostVul803NwmaxMatrixNearRelative left right absoluteTolerance relativeTolerance =
(
    ghostVul803NwmaxPointNearRelative left.row1 right.row1 absoluteTolerance relativeTolerance and \
    ghostVul803NwmaxPointNearRelative left.row2 right.row2 absoluteTolerance relativeTolerance and \
    ghostVul803NwmaxPointNearRelative left.row3 right.row3 absoluteTolerance relativeTolerance and \
    ghostVul803NwmaxPointNearRelative left.row4 right.row4 absoluteTolerance relativeTolerance
)


fn ghostVul803NwmaxWorldMeshSnapshot node =
(
    local evaluated = undefined
    local errorText = undefined
    local snapshot = undefined
    try
    (
        evaluated = snapshotAsMesh node
        -- snapshotAsMesh returns the evaluated world-state TriMesh. Applying
        -- node/objectTransform again would double-transform scaled legacy data.
        local vertices = for vertexIndex = 1 to evaluated.numverts collect \
            (copy (getVert evaluated vertexIndex))
        local faces = for faceIndex = 1 to evaluated.numfaces collect \
            (copy (getFace evaluated faceIndex))
        local materialIds = for faceIndex = 1 to evaluated.numfaces collect \
            (getFaceMatID evaluated faceIndex)
        local smoothingGroups = for faceIndex = 1 to evaluated.numfaces collect \
            (getFaceSmoothGroup evaluated faceIndex)
        local edgeVisibility = for faceIndex = 1 to evaluated.numfaces collect \
            #(
                getEdgeVis evaluated faceIndex 1,
                getEdgeVis evaluated faceIndex 2,
                getEdgeVis evaluated faceIndex 3
            )
        local mapChannels = #()
        local mapCount = meshop.getNumMaps evaluated
        for mapChannel = 0 to (mapCount - 1) where meshop.getMapSupport evaluated mapChannel do
        (
            local mapVertexCount = meshop.getNumMapVerts evaluated mapChannel
            local mapFaceCount = meshop.getNumMapFaces evaluated mapChannel
            local mapVertices = for mapVertexIndex = 1 to mapVertexCount collect \
                (copy (meshop.getMapVert evaluated mapChannel mapVertexIndex))
            local mapFaces = for mapFaceIndex = 1 to mapFaceCount collect \
                (copy (meshop.getMapFace evaluated mapChannel mapFaceIndex))
            append mapChannels #(mapChannel, mapVertices, mapFaces)
        )
        snapshot = #(
            vertices, faces, materialIds, smoothingGroups, edgeVisibility, mapChannels
        )
    )
    catch
    (
        errorText = getCurrentException() as string
    )
    if evaluated != undefined do delete evaluated
    if errorText != undefined then throw ("Could not snapshot evaluated mesh for " + node.name + ": " + errorText)
    snapshot
)


fn ghostVul803NwmaxPointArraysNear left right absoluteTolerance relativeTolerance =
(
    if left.count != right.count then return false
    for index = 1 to left.count where \
        not ghostVul803NwmaxPointNearRelative left[index] right[index] absoluteTolerance relativeTolerance do return false
    true
)


fn ghostVul803NwmaxPointArraysMaximumDelta left right =
(
    if left.count != right.count then return undefined
    local maximumDelta = 0.0
    for index = 1 to left.count do
    (
        local difference = left[index] - right[index]
        if abs difference.x > maximumDelta do maximumDelta = abs difference.x
        if abs difference.y > maximumDelta do maximumDelta = abs difference.y
        if abs difference.z > maximumDelta do maximumDelta = abs difference.z
    )
    maximumDelta
)


fn ghostVul803NwmaxPointArraysExact left right =
(
    if left.count != right.count then return false
    for index = 1 to left.count do
    (
        local leftValue = left[index]
        local rightValue = right[index]
        if leftValue.x != rightValue.x or leftValue.y != rightValue.y or leftValue.z != rightValue.z then return false
    )
    true
)


fn ghostVul803NwmaxArraysExact left right =
(
    if left.count != right.count then return false
    for index = 1 to left.count where left[index] != right[index] do return false
    true
)


fn ghostVul803NwmaxNestedArraysExact left right =
(
    if left.count != right.count then return false
    for outerIndex = 1 to left.count do
    (
        if left[outerIndex].count != right[outerIndex].count then return false
        for innerIndex = 1 to left[outerIndex].count where \
            left[outerIndex][innerIndex] != right[outerIndex][innerIndex] do return false
    )
    true
)


fn ghostVul803NwmaxMapChannelsMatch left right =
(
    if left.count != right.count then return false
    for channelIndex = 1 to left.count do
    (
        if left[channelIndex][1] != right[channelIndex][1] then return false
        if not ghostVul803NwmaxPointArraysNear \
            left[channelIndex][2] right[channelIndex][2] 0.000001 0.000001 then return false
        if not ghostVul803NwmaxPointArraysExact \
            left[channelIndex][3] right[channelIndex][3] then return false
    )
    true
)


fn ghostVul803NwmaxWorldMeshSnapshotsMatch before after =
(
    ghostVul803NwmaxPointArraysNear before[1] after[1] 0.05 0.000001 and \
    ghostVul803NwmaxPointArraysExact before[2] after[2] and \
    ghostVul803NwmaxArraysExact before[3] after[3] and \
    ghostVul803NwmaxArraysExact before[4] after[4] and \
    ghostVul803NwmaxNestedArraysExact before[5] after[5] and \
    ghostVul803NwmaxMapChannelsMatch before[6] after[6]
)


fn ghostVul803NwmaxNormalizeNamedScales base nodeNames reportPath =
(
    -- This repair is intentionally opt-in and is only used on the run-owned
    -- in-memory copy loaded by 3dsMaxMCP. resetXForm bakes a node's scale into
    -- an XForm modifier while preserving its world-space bounds. The batch
    -- process exits without saving the staged .max scene.
    if nodeNames.count == 0 then return true
    if ghostVul803NwmaxFileExists reportPath then
    (
        ghostVul803NwmaxLog ("Refusing to overwrite transform-normalization report: " + reportPath)
        return false
    )

    local roomNodes = #(base)
    ghostVul803NwmaxCollectTree base roomNodes
    local report = undefined
    local errorText = undefined
    local targetNodes = #()
    local roomRecords = for node in roomNodes collect
    (
        local bounds = undefined
        local evaluatedSnapshot = undefined
        try (bounds = nodeGetBoundingBox node (matrix3 1)) catch ()
        try (evaluatedSnapshot = ghostVul803NwmaxWorldMeshSnapshot node) catch ()
        #(node, copy node.transform, bounds, evaluatedSnapshot)
    )

    try
    (
        report = createFile reportPath
        if report == undefined then throw ("Cannot create transform-normalization report: " + reportPath)
        format "room=%\noperation=resetXForm\nscene_saved=false\n" base.name to:report

        for nodeName in nodeNames do
        (
            local matches = #()
            for node in roomNodes where node.name == nodeName do append matches node
            if matches.count != 1 then
                throw ("Scale-normalization node " + nodeName + " resolved " + (matches.count as string) + " times inside " + base.name)

            local target = matches[1]
            if target.children.count != 0 then
                throw ("Refusing resetXForm on non-leaf node " + target.name + " with " + (target.children.count as string) + " child node(s)")

            local instanceNodes = #()
            local instanceQueryOk = true
            try (InstanceMgr.GetInstances target &instanceNodes) catch (instanceQueryOk = false)
            if not instanceQueryOk then
                throw ("Could not prove instance isolation for " + target.name)
            if instanceNodes.count != 1 or instanceNodes[1] != target then
                throw ("Refusing resetXForm on shared object pipeline " + target.name + "; instance count " + (instanceNodes.count as string))
            if ghostVul803NwmaxTransformHasKeys target then
                throw ("Refusing resetXForm on animated or procedural node: " + target.name)

            local beforeScale = copy target.scale
            local beforeBounds = nodeGetBoundingBox target (matrix3 1)
            local beforeMesh = ghostVul803NwmaxWorldMeshSnapshot target
            if not ghostVul803NwmaxUnitScale beforeScale then resetXForm target
            local afterScale = copy target.scale
            local afterBounds = nodeGetBoundingBox target (matrix3 1)
            local afterMesh = ghostVul803NwmaxWorldMeshSnapshot target

            format "node=%\nhandle=%\nposition_controller=%\nrotation_controller=%\nscale_controller=%\ntransform_static=true\nleaf=true\ninstance_count=%\nbefore_scale=%\nafter_scale=%\nbefore_bounds=%\nafter_bounds=%\n" \
                target.name target.handle ((classOf target.position.controller) as string) \
                ((classOf target.rotation.controller) as string) \
                ((classOf target.scale.controller) as string) instanceNodes.count \
                beforeScale afterScale beforeBounds afterBounds to:report
            flush report

            if not ghostVul803NwmaxUnitScale afterScale then
                throw ("resetXForm did not produce unit scale for " + target.name + ": " + (afterScale as string))
            if not ghostVul803NwmaxPointNearRelative beforeBounds[1] afterBounds[1] 0.05 0.000001 or \
               not ghostVul803NwmaxPointNearRelative beforeBounds[2] afterBounds[2] 0.05 0.000001 then
                throw ("resetXForm changed world-space bounds for " + target.name)
            if not ghostVul803NwmaxWorldMeshSnapshotsMatch beforeMesh afterMesh then
            (
                ghostVul803NwmaxLog ("Export-channel comparison for " + target.name + \
                    ": world_vertices=" + ((ghostVul803NwmaxPointArraysNear beforeMesh[1] afterMesh[1] 0.05 0.000001) as string) + \
                    ", topology=" + ((ghostVul803NwmaxPointArraysExact beforeMesh[2] afterMesh[2]) as string) + \
                    ", material_ids=" + ((ghostVul803NwmaxArraysExact beforeMesh[3] afterMesh[3]) as string) + \
                    ", smoothing=" + ((ghostVul803NwmaxArraysExact beforeMesh[4] afterMesh[4]) as string) + \
                    ", edge_visibility=" + ((ghostVul803NwmaxNestedArraysExact beforeMesh[5] afterMesh[5]) as string) + \
                    ", map_channels=" + ((ghostVul803NwmaxMapChannelsMatch beforeMesh[6] afterMesh[6]) as string) + \
                    ", maximum_world_vertex_delta=" + ((ghostVul803NwmaxPointArraysMaximumDelta beforeMesh[1] afterMesh[1]) as string))
                throw ("resetXForm changed evaluated world vertices, topology, material IDs, smoothing groups, edge visibility, or map channels for " + target.name)
            )

            append targetNodes target
            format "bounds_preserved=true\nevaluated_export_channels_preserved=true\nbounds_tolerance_absolute=0.05\nbounds_tolerance_relative=0.000001\n" to:report
        )

        for roomRecord in roomRecords do
        (
            local roomNode = roomRecord[1]
            if not isValidNode roomNode then throw "A room node became invalid during transform normalization."
            if findItem targetNodes roomNode == 0 and \
               not ghostVul803NwmaxMatrixNearRelative roomRecord[2] roomNode.transform 0.001 0.000001 then
                throw ("Transform normalization changed unregistered node transform: " + roomNode.name)
            if roomRecord[3] != undefined then
            (
                local finalBounds = undefined
                try (finalBounds = nodeGetBoundingBox roomNode (matrix3 1)) catch ()
                if finalBounds == undefined or \
                   not ghostVul803NwmaxPointNearRelative roomRecord[3][1] finalBounds[1] 0.05 0.000001 or \
                   not ghostVul803NwmaxPointNearRelative roomRecord[3][2] finalBounds[2] 0.05 0.000001 then
                    throw ("Transform normalization changed room-node world bounds: " + roomNode.name)
            )
            if roomRecord[4] != undefined then
            (
                local finalSnapshot = undefined
                try (finalSnapshot = ghostVul803NwmaxWorldMeshSnapshot roomNode) catch ()
                if finalSnapshot == undefined or \
                   not ghostVul803NwmaxWorldMeshSnapshotsMatch roomRecord[4] finalSnapshot then
                    throw ("Transform normalization changed room-node evaluated export channels: " + roomNode.name)
            )
        )
        format "registered_node_count=%\nroom_node_count=%\nroom_nodes_preserved=true\n" \
            targetNodes.count roomNodes.count to:report
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
    if errorText != undefined then
    (
        ghostVul803NwmaxLog ("Transform normalization failed: " + errorText)
        return false
    )

    ghostVul803NwmaxLog ("Normalized " + (nodeNames.count as string) + " explicitly registered non-unit scale node(s) without changing verified room export channels.")
    true
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
    local readError = undefined

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
        readError = getCurrentException() as string
    )

    if stream != undefined do close stream
    if readError != undefined then
        throw ("Failed to read sanity report " + sanityReport + ": " + readError)
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
    if toLower (nx_strclassof base) != "aurorabase" then
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


fn ghostVul803NwmaxExportExistingRoot roomName outputDirectory allowSanityFailure:false resetXformNodes:#() =
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
    local normalizationPath = ghostVul803NwmaxCombinePath outputDirectory (roomName + "_transform_normalization.txt")

    if isProperty base #export_path do base.export_path = outputDirectory
    if ghostVul803NwmaxNormalizeNamedScales base resetXformNodes normalizationPath then
        result = ghostVul803NwmaxExportBase base outputDirectory allowSanityFailure:allowSanityFailure
    if priorExportPath != undefined do base.export_path = priorExportPath
    result
)


fn ghostVul803NwmaxExportManifest roomName sanityReport outputDirectory allowSanityFailure:false replaceExistingRoot:false resetXformNodes:#() =
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
                if ghostVul803NwmaxTransformHasKeys node then
                    throw ("Refusing to reparent animated, procedural, or unrecognized-controller top-level manifest node: " + node.name + \
                        " [position=" + ((classOf node.position.controller) as string) + \
                        ", rotation=" + ((classOf node.rotation.controller) as string) + \
                        ", scale=" + ((classOf node.scale.controller) as string) + "]")
                local worldTM = copy (at time 0 node.transform)
                append changedParents #(node, node.parent, worldTM)
                with animate off
                (
                    node.parent = base
                    at time 0 node.transform = worldTM
                )
            )
        )

        local normalizationPath = ghostVul803NwmaxCombinePath outputDirectory (roomName + "_transform_normalization.txt")
        if ghostVul803NwmaxNormalizeNamedScales base resetXformNodes normalizationPath then
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
