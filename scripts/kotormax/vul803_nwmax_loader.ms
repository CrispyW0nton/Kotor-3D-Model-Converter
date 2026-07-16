-- Ghost Studio - guarded NWMax 0.8 b60 loader for the vul803 Max 9 scenes
--
-- Stage the preserved NWmax folder under the active 3ds Max scripts directory
-- returned by `getDir #scripts`, run this script before opening a scene, then call:
--
--     ghostVul803LoadLegacyNwmax()
--
-- This loader does not open or save a scene.  It refuses to mix KOTORMax and
-- NWMax in one process and verifies that the legacy exporter core survived any
-- late, version-specific NWMax UI error.

global ExportOdysseyModel
global kx_exportmodelsilent
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
global gblVersion
global g_ismax
global autostart


fn ghostVul803NwmaxLoaderLog message =
(
    format "[Ghost Studio vul803/NWMax loader] %\n" message
)


fn ghostVul803LegacyNwmaxCoreIsReady =
(
    ExAuroraMDL != undefined and SanityCheck != undefined and \
    nx_strclassof != undefined and AuroraBase != undefined and \
    AuroraTrimesh != undefined and AuroraFlex != undefined and \
    AuroraWalkmesh != undefined and AuroraLight != undefined and \
    AuroraDLight != undefined and AuroraEmitter != undefined and \
    AuroraReference != undefined and \
    gblVersion == "0.8 b60" and g_ismax == true
)


fn ghostVul803LoadLegacyNwmax =
(
    if ExportOdysseyModel != undefined or kx_exportmodelsilent != undefined then
    (
        ghostVul803NwmaxLoaderLog "KOTORMax is already loaded. Restart 3ds Max; never mix KOTORMax and NWMax in one process."
        return false
    )

    if ghostVul803LegacyNwmaxCoreIsReady() then
    (
        ghostVul803NwmaxLoaderLog "Legacy NWMax 0.8 b60 is already ready."
        return true
    )

    -- A partial scripted-plugin load cannot be repaired safely in place because
    -- Max retains class definitions for the life of the process.
    if AuroraBase != undefined or AuroraDLight != undefined or gblVersion == "0.8 b60" then
    (
        ghostVul803NwmaxLoaderLog "A partial NWMax load is present. Restart 3ds Max before retrying."
        return false
    )

    local scriptsDirectory = getDir #scripts
    local nwmaxDirectory = scriptsDirectory + "\\NWmax"
    local nwmaxScript = nwmaxDirectory + "\\nwmax.ms"
    local nwmaxIni = nwmaxDirectory + "\\nwmax.ini"

    if not doesFileExist nwmaxScript then
    (
        ghostVul803NwmaxLoaderLog ("Missing staged NWMax script: " + nwmaxScript)
        return false
    )
    if not doesFileExist nwmaxIni then
    (
        ghostVul803NwmaxLoaderLog ("Missing staged NWMax configuration: " + nwmaxIni)
        return false
    )
    if getINISetting nwmaxIni "init" "usemax" != "1" then
    (
        ghostVul803NwmaxLoaderLog "NWmax.ini is not configured for 3ds Max. Set [init] usemax=1 and restart."
        return false
    )
    if getINISetting nwmaxIni "init" "visible" != "0" do
    (
        ghostVul803NwmaxLoaderLog "Compatibility note: set [init] visible=0 and dock=0 in the staged NWmax.ini; the guarded exporter does not need the legacy floater UI."
    )

    local loadError = undefined
    autostart = true
    try
    (
        fileIn nwmaxScript
    )
    catch
    (
        loadError = getCurrentException() as string
    )

    if not ghostVul803LegacyNwmaxCoreIsReady() then
    (
        if loadError != undefined do ghostVul803NwmaxLoaderLog ("NWMax load error: " + loadError)
        ghostVul803NwmaxLoaderLog "The complete legacy exporter core did not load. Restart 3ds Max before another attempt."
        return false
    )

    if loadError != undefined do
    (
        ghostVul803NwmaxLoaderLog ("NWMax core loaded, but its optional legacy UI tail reported: " + loadError)
    )

    ghostVul803NwmaxLoaderLog "Legacy NWMax 0.8 b60 exporter core is ready. Open only a COPY of the Max 9 source scene."
    true
)


ghostVul803NwmaxLoaderLog "Guarded loader ready; no toolset or scene was loaded automatically."
