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
    /// Used to insert a new column into a TwoDA instance.
    /// </summary>
    public class AddColumn2DAModifier : IModifier<TwoDA>
    {
        /// <summary>
        /// The header for the column that is to be inserted.
        /// </summary>
        public string ColumnHeader { get; }
        /// <summary>
        /// The default value for all the cells under the new column.
        /// </summary>
        public string DefaultValue { get; }

        public Dictionary<ITarget, IValue> Values { get; set; }

        public Dictionary<int, IValue> ToStoreInMemory { get; set; }


        public AddColumn2DAModifier(string header, string defaultValue, Dictionary<ITarget, IValue> values, Dictionary<int, IValue> toStoreInMemory)
        {
            ColumnHeader = header;
            DefaultValue = defaultValue;
            Values = values;
            ToStoreInMemory = toStoreInMemory;
        }

        public void Apply(TwoDA twoda, IMemory memory, ILogger logger)
        {
            try
            {
                twoda.AddColumn(ColumnHeader);

                foreach (var row in twoda.Rows())
                {
                    row.SetCell(ColumnHeader, DefaultValue);
                }

                foreach (var (key, value) in Values)
                {
                    var row = key.Search(twoda);
                    var text = value.GetValue(memory, logger, twoda, row, ColumnHeader);

                    row.SetCell(ColumnHeader, text);
                }

                foreach (var (tokenID, value) in ToStoreInMemory)
                {
                    var text = value.GetValue(memory, logger, twoda, null, ColumnHeader);

                    if (memory.From2DAToken(tokenID) is not null)
                    {
                        logger.Warning($"Overriding existing 2DAMEMORY{tokenID} value.");
                    }

                    memory.Set2DAToken(tokenID, text);
                }
            }
            catch (ApplyModifierException ex)
            {
                logger.Error(ex.Message);
            }
        }
    }
}
