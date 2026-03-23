using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Data
{
    /// <summary>
    /// A special class designed to store a path that accounts for the case-sensitivity
    /// on unix-like systems.
    /// </summary>
    public class KotorPath
    {
        /// <summary>
        /// The stored path.
        /// </summary>
        public string Value { get; private set; }

        public KotorPath(string path)
        {
            // TODO - check casing on unix systems
            Value = path;
        }

        /// <summary>
        /// Returns a new KotorPath instance with the specificied path adjoined to
        /// the end of the current instance.
        /// </summary>
        /// <param name="path">The extra path to add to the end.</param>
        /// <returns>A new KotorPath instance with the old and new paths joined.</returns>
        public KotorPath Join(string path)
        {
            return Path.Join(Value, path);
        }

        public static implicit operator KotorPath(string path)
        {
            return new KotorPath(path);
        }

        public static implicit operator string(KotorPath path)
        {
            return path.Value;
        }
    }
}
