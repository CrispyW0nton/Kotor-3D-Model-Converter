using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Targets
{
    /// <summary>
    /// Gets a TwoDARow from a TwoDA. How which row is determined is up to the
    /// implementation.
    /// </summary>
    public interface ITarget
    {
        /// <summary>
        /// Search for a particular row in a given TwoDA instance. What is
        /// being searched for is up to the implementation of the interface.
        /// </summary>
        /// <param name="twoda">The TwoDA instance to search in.</param>
        /// <returns>A row in the given TwoDA instance.</returns>
        TwoDARow Search(TwoDA twoda);
    }
}
