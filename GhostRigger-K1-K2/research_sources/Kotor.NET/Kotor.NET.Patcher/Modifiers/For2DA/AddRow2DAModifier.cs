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
    /// Used to insert a row into a TwoDA instance.
    /// </summary>
    public class AddRow2DAModifier : IModifier<TwoDA>
    {
        /// <summary>
        /// If assigned a non-null value, a new row will only be inserted if there
        /// is no existing row containing the the same value as this column. If a
        /// match is found then the existing row is to be modified instead. 
        /// </summary>
        public string? ExclusiveColumn { get; set; }
        /// <summary>
        /// The value generator to be used to get the row header. If this value is
        /// null then the row index will be used instead.
        /// </summary>
        public IValue? RowHeader { get; set; }
        /// <summary>
        /// Maps column headers (Keys) to cell values.
        /// </summary>
        public Dictionary<string, IValue> Data { get; set; }
        /// <summary>
        /// Maps token IDs (Keys) to values.
        /// </summary>
        public Dictionary<int, IValue> ToStoreInMemory { get; set; }

        public AddRow2DAModifier(string? exclusiveColumn, IValue? rowLabel, Dictionary<string, IValue> data, Dictionary<int, IValue> toStore)
        {
            ExclusiveColumn = exclusiveColumn;
            RowHeader = rowLabel;
            Data = data;
            ToStoreInMemory = toStore;
        }

        public void Apply(TwoDA twoda, IMemory memory, ILogger logger)
        {
            try
            {
                TwoDARow row;
                string RowLabelIfNew = twoda.Rows().Count.ToString();
                bool isNew = false;

                if (ExclusiveColumn == null)
                {
                    row = twoda.AddRow(RowLabelIfNew);
                    isNew = true;
                }
                else
                {
                    if (twoda.ColumnHeaders().Contains(ExclusiveColumn) && Data.Keys.Contains(ExclusiveColumn))
                    {
                        var cells = twoda.GetCellsUnderColumn(ExclusiveColumn).ToList();
                        var exclusiveValue = Data[ExclusiveColumn].GetValue(memory, logger, twoda, null, null);

                        if (cells.Contains(exclusiveValue))
                        {
                            row = twoda.Rows()[cells.IndexOf(exclusiveValue)];
                        }
                        else
                        {
                            row = twoda.AddRow(RowLabelIfNew);
                            isNew = true;
                        }
                    }
                    else
                    {
                        row = twoda.AddRow(RowLabelIfNew);
                        isNew = true;
                    }
                }

                if (RowHeader != null)
                {
                    row.Header = RowHeader.GetValue(memory, logger, twoda, row, null);
                }

                if (isNew)
                {
                    foreach (var columnHeader in twoda.ColumnHeaders())
                    {
                        row.SetCell(columnHeader, "");
                    }
                }

                foreach (var pair in Data)
                {
                    var columnHeader = pair.Key;
                    var cellValue = pair.Value;

                    if (twoda.ColumnHeaders().Contains(columnHeader))
                    {
                        var value = cellValue.GetValue(memory, logger, twoda, row, columnHeader);
                        row.SetCell(columnHeader, value);
                    }
                }

                foreach (var toStore in ToStoreInMemory)
                {
                    var tokenID = toStore.Key;

                    if (memory.From2DAToken(tokenID) is not null)
                    {
                        logger.Warning($"Overriding existing 2DAMEMORY{tokenID} value.");
                    }

                    var value = toStore.Value.GetValue(memory, logger, twoda, row, null);
                    memory.Set2DAToken(tokenID, value);
                }
            }
            catch (ApplyModifierException ex)
            {
                logger.Error(ex.Message);
            }
        }
    }
}
