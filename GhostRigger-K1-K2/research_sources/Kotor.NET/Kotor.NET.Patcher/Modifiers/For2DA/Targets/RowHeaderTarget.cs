using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Targets
{
    /// <summary>
    /// Searches for a row in a TwoDA class that matches a stored row header.
    /// </summary>
    public class RowHeaderTarget : ITarget
    {
        /// <summary>
        /// The row header that will be searched for.
        /// </summary>
        public string RowHeader { get; set; }

        public RowHeaderTarget(string rowHeader)
        {
            RowHeader = rowHeader;
        }

        public TwoDARow Search(TwoDA twoda)
        {
            var row = twoda.Row(RowHeader);

            if (row is not null)
            {
                return row;
            }
            else
            {
                throw new ApplyModifierException($"Could not find row with header {RowHeader}.");
            }
        }
    }
}
