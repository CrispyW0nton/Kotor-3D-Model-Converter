using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers
{
    public class Log
    {
        public DateTime Timestamp { get; init; }
        public LogLevel LogLevel { get; init; }
        public string Text { get; init; }

        public Log(LogLevel logLevel, string text)
        {
            Timestamp = DateTime.Now;
            LogLevel = logLevel;
            Text = text;
        }
    }
}
