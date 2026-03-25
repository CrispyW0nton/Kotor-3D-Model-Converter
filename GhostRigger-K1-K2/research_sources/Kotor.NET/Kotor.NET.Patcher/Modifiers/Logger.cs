using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers
{
    public class Logger : ILogger
    {
        public ObservableCollection<Log> Logs { get; set; } = new();

        public void Verbose(string message)
        {
            Logs.Add(new Log(LogLevel.Verbose, message));
        }

        public void Information(string message)
        {
            Logs.Add(new Log(LogLevel.Information, message));
        }

        public void Warning(string message)
        {
            Logs.Add(new Log(LogLevel.Warning, message));
        }

        public void Error(string message)
        {
            Logs.Add(new Log(LogLevel.Error, message));
        }
    }
}
