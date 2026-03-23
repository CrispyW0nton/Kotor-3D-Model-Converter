using Kotor.NET.Patcher.Parsers.LegacyINI;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Parsers.INI
{
    /// <summary>
    /// For Parsing changes.ini to a PatcherData instance following
    /// Stoffe's TSLPatcher specifications as well as introducing
    /// new some new functionality.
    /// </summary>
    public class INIParser : LegacyINIReader
    {
        public INIParser(string iniText) : base(iniText)
        {

        }
    }
}
