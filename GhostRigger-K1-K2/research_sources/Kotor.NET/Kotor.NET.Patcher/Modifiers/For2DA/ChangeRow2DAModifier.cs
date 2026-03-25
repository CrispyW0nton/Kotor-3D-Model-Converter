using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patcher.Modifiers.For2DA.Targets;
using Kotor.NET.Patcher.Modifiers.For2DA.Values;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA
{
    /// <summary>
    /// Used to edit a row in a TwoDA instance.
    /// </summary>
    public class ChangeRow2DAModifier : IModifier<TwoDA>
    {
        /// <summary>
        /// The target row to copy.
        /// </summary>
        public ITarget ITarget { get; set; }
        /// <summary>
        /// Maps column headers (Keys) to cell values.
        /// </summary>
        public Dictionary<string, IValue> Data { get; set; }
        /// <summary>
        /// Maps token IDs (Keys) to values.
        /// </summary>
        public Dictionary<int, IValue> ToStoreInMemory { get; set; }

        public ChangeRow2DAModifier(ITarget target, Dictionary<string, IValue> data, Dictionary<int, IValue> toStoreInMemory)
        {
            ITarget = target;
            Data = data;
            ToStoreInMemory = toStoreInMemory;
        }

        public void Apply(TwoDA twoda, IMemory memory, ILogger logger)
        {
            try
            {
                var source = ITarget.Search(twoda);

                foreach (var pair in Data)
                {
                    var columnHeader = pair.Key;
                    var cellValue = pair.Value;

                    if (twoda.ColumnHeaders().Contains(columnHeader))
                    {
                        var value = cellValue.GetValue(memory, logger, twoda, source, columnHeader);
                        source.SetCell(columnHeader, value);
                    }
                }

                foreach (var toStore in ToStoreInMemory)
                {
                    var value = toStore.Value.GetValue(memory, logger, twoda, source, null);
                    memory.Set2DAToken(toStore.Key, value);
                }
            }
            catch (ApplyModifierException ex)
            {
                logger.Error(ex.Message);
            }
        }
    }
}
