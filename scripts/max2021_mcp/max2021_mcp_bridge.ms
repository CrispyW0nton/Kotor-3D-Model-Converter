-- 3ds Max 2021 MCP Socket Bridge
--
-- Listens on a TCP port for JSON tool payloads and executes MaxScript through
-- `execute`, then returns a JSON response for the GhostRigger max2021 MCP socket
-- adapter.

global max2021McpBridgeRunning = false
global max2021McpBridgeHost = "127.0.0.1"
global max2021McpBridgePort = 19001
global max2021McpBridgeListener = undefined
global max2021McpBridgeThread = undefined
global max2021McpBridgeAutoStart = true


fn max2021McpBridgeReadEnvInt name defaultValue =
(
    local raw = getEnvVariable name
    if raw == undefined or raw == "" then return defaultValue
    try
    (
        return (raw as integer)
    )
    catch
    (
        return defaultValue
    )
)


fn max2021McpBridgeJsonEscape value =
(
    local text = if value == undefined then "" else (value as string)
    text = substituteString text "\\" "\\\\"
    text = substituteString text "\"" "\\\""
    text = substituteString text "\r" "\\r"
    text = substituteString text "\n" "\\n"
    text = substituteString text "\t" "\\t"
    text
)


fn max2021McpBridgeExtractField jsonText fieldName =
(
    local marker = "\"" + fieldName + "\""
    local markerPos = findString jsonText marker
    if markerPos == 0 then return undefined

    local i = markerPos + marker.count
    local length = jsonText.count
    while (i <= length and (jsonText[i] != ":")) do (i += 1)
    if i > length then return undefined
    i += 1

    while
    (
        i <= length and
        (jsonText[i] == " " or jsonText[i] == "\t" or jsonText[i] == "\r" or jsonText[i] == "\n")
    ) do (i += 1)
    if i > length or jsonText[i] != "\"" then return undefined
    i += 1

    local output = ""
    local escaped = false
    while i <= length do
    (
        local ch = jsonText[i]
        if escaped then
        (
            case ch of
            (
                "\"" : output += "\""
                "\\" : output += "\\"
                "/" : output += "/"
                "b" : output += "\b"
                "f" : output += "\f"
                "n" : output += "\n"
                "r" : output += "\r"
                "t" : output += "\t"
                "u" :
                (
                    if i + 4 <= length then
                    (
                        local hex = substring jsonText (i + 1) 4
                        i += 4
                        output += "\\u" + hex
                    )
                    else
                    (
                        output += "u"
                    )
                )
                default : output += ch
            )
            escaped = false
        )
        else if ch == "\\" then
        (
            escaped = true
        )
        else if ch == "\"" then
        (
            exit
        )
        else
        (
            output += ch
        )
        i += 1
    )
    output
)


fn max2021McpBridgeReadAll stream =
(
    local encoding = (dotNetClass "System.Text.Encoding").UTF8
    local buffer = dotNetObject "System.Byte[]" 4096
    local payload = ""
    while true do
    (
        local count = 0
        try
        (
            count = stream.Read buffer 0 buffer.Length
        )
        catch
        (
            count = 0
        )
        if count <= 0 then exit
        payload += encoding.GetString buffer 0 count
    )
    payload
)


fn max2021McpBridgeSendResponse stream requestId text isError =
(
    if requestId == undefined do requestId = "max2021-unknown"
    if text == undefined do text = ""
    local payload =
        "{"
        + "\"id\": \"" + requestId + "\","
        + "\"text\": \"" + max2021McpBridgeJsonEscape text + "\","
        + "\"is_error\": " + (if isError then "true" else "false")
        + "}"
        + "\n"

    local bytes = (dotNetClass "System.Text.Encoding").UTF8.GetBytes payload
    stream.Write bytes 0 bytes.Length
    stream.Flush()
)


fn max2021McpBridgeToText value =
(
    if value == undefined then return ""
    try
    (
        return (value as string)
    )
    catch
    (
        return ""
    )
)


fn max2021McpBridgeExecuteScript scriptText =
(
    local resultText = ""
    local isError = false
    local result = undefined
    try
    (
        result = execute scriptText
        resultText = if result == undefined then "OK" else max2021McpBridgeToText result
    )
    catch
    (
        local ex = getCurrentException()
        isError = true
        resultText = "MaxScript execution failed: " + (max2021McpBridgeToText ex)
    )
    #(resultText, isError)
)


fn max2021McpBridgeHandleClient client =
(
    local requestId = "max2021-unknown"
    local stream = undefined
    local requestText = ""
    local responseText = ""
    local isError = false
    try
    (
        stream = client.GetStream()
        requestText = max2021McpBridgeReadAll stream
        if requestText == "" then
        (
            isError = true
            responseText = "Received empty socket payload."
        )
        else
        (
            local parsedId = max2021McpBridgeExtractField requestText "id"
            if parsedId != undefined do requestId = parsedId

            local scriptText = max2021McpBridgeExtractField requestText "script"
            if scriptText == undefined then
            (
                isError = true
                responseText = "Missing or malformed JSON field 'script'."
            )
            else
            (
                local result = max2021McpBridgeExecuteScript scriptText
                responseText = result[1]
                isError = result[2]
            )
        )
    )
    catch
    (
        local ex = getCurrentException()
        isError = true
        responseText = "Socket handler failed: " + (max2021McpBridgeToText ex)
    )

    if stream != undefined then
    (
        try
        (
            max2021McpBridgeSendResponse stream requestId responseText isError
        )
        catch
        (
            ()
        )
        try
        (
            stream.Close()
        )
        catch
        (
            ()
        )
    )
)


fn max2021McpBridgeAcceptLoop =
(
    while max2021McpBridgeRunning do
    (
        local client = undefined
        try
        (
            if max2021McpBridgeListener == undefined do exit
            client = max2021McpBridgeListener.AcceptTcpClient()
        )
        catch
        (
            if max2021McpBridgeRunning then
            (
                print ("3ds Max MCP bridge accept failed: " + (max2021McpBridgeToText (getCurrentException())))
            )
            client = undefined
        )

        if client != undefined do
        (
            max2021McpBridgeHandleClient client
            try
            (
                client.Close()
            )
            catch
            (
                ()
            )
        )
    )

    try
    (
        if max2021McpBridgeListener != undefined then max2021McpBridgeListener.Stop()
    )
    catch
    (
        ()
    )
)


fn max2021McpBridgeStart =
(
    if max2021McpBridgeRunning then return false

    local host = getEnvVariable "MAX2021_MCP_HOST"
    local port = max2021McpBridgeReadEnvInt "MAX2021_MCP_PORT" 19001
    max2021McpBridgePort = if port <= 0 then 19001 else port
    max2021McpBridgeHost = if host == undefined or host == "" then "127.0.0.1" else host

    try
    (
        local ipAddress = (dotNetClass "System.Net.IPAddress").Parse max2021McpBridgeHost
        max2021McpBridgeListener = dotNetObject "System.Net.Sockets.TcpListener" ipAddress max2021McpBridgePort
        max2021McpBridgeListener.Start()
        max2021McpBridgeRunning = true

        local worker = dotNetObject "System.Threading.ThreadStart" max2021McpBridgeAcceptLoop
        max2021McpBridgeThread = dotNetObject "System.Threading.Thread" worker
        max2021McpBridgeThread.IsBackground = true
        max2021McpBridgeThread.Start()

        format "3ds Max 2021 MCP bridge started on %:%\n" max2021McpBridgeHost max2021McpBridgePort
        return true
    )
    catch
    (
        max2021McpBridgeRunning = false
        max2021McpBridgeListener = undefined
        print ("3ds Max MCP bridge failed to start: " + (max2021McpBridgeToText (getCurrentException())))
        return false
    )
)


fn max2021McpBridgeStop =
(
    if not max2021McpBridgeRunning and max2021McpBridgeListener == undefined then return false

    max2021McpBridgeRunning = false
    try
    (
        if max2021McpBridgeListener != undefined then max2021McpBridgeListener.Stop()
    )
    catch
    (
        ()
    )

    try
    (
        if max2021McpBridgeThread != undefined and max2021McpBridgeThread.IsAlive then
        (
            max2021McpBridgeThread.Join 200
        )
    )
    catch
    (
        ()
    )

    max2021McpBridgeListener = undefined
    max2021McpBridgeThread = undefined
    format "3ds Max 2021 MCP bridge stopped on %:%\n" max2021McpBridgeHost max2021McpBridgePort
    true
)


fn max2021McpBridgeGetStatus =
(
    local state = if max2021McpBridgeRunning then "running" else "stopped"
    local threadState = "none"
    if max2021McpBridgeThread != undefined do threadState = if max2021McpBridgeThread.IsAlive then "alive" else "stopped"
    #(
        #("status", state),
        #("host", max2021McpBridgeHost),
        #("port", max2021McpBridgePort),
        #("thread", threadState),
        #("listener", max2021McpBridgeListener != undefined)
    )
)


if max2021McpBridgeAutoStart do
(
    max2021McpBridgeStart()
)
