using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher
{
    public class ModifyFile<T>
    {
        /// <summary>
        /// Where to save the file to. This can either be a folder or a path to
        /// a MOD file.
        /// </summary>
        public string Destination { get; set; } = "";
        /// <summary>
        /// Name of the filename to save inside the given destination.
        /// </summary>
        public string FileName { get; set; } = "";
        /// <summary>
        /// List of modifiers to apply to the file.
        /// </summary>
        public List<IModifier<T>> Modifiers { get; set; } = new();
        /// <summary>
        /// If a file exists in the destination with the same filename, then this
        /// will determine if the existing file will be overriden.
        /// </summary>
        public bool OverrideExisting { get; set; }
    }
}
