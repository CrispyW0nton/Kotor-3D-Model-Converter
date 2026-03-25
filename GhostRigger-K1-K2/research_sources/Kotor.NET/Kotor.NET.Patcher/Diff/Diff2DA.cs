using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patcher.Modifiers.For2DA;
using Kotor.NET.Patcher.Modifiers.For2DA.Targets;
using Kotor.NET.Patcher.Modifiers.For2DA.Values;

namespace Kotor.NET.Patcher.Diff
{
    public class Diff2DA
    {
        public TwoDA Older { get; }
        public TwoDA Newer { get; }

        public Diff2DA(TwoDA older, TwoDA newer)
        {
            Older = older;
            Newer = newer;
        }

        public List<IModifier<TwoDA>> Find()
        {
            var modifiers = new List<IModifier<TwoDA>>();

            var oldColumnHeaders = new HashSet<string>(Older.ColumnHeaders());
            var newColumnHeaders = new HashSet<string>(Newer.ColumnHeaders());
            var addedColumnHeaders = newColumnHeaders.Except(oldColumnHeaders);
            var defaultCellValue = "";
            foreach (var addedColumnHeader in addedColumnHeaders)
            {
                var values = new Dictionary<ITarget, IValue>();
                foreach (var row in Newer.Rows())
                {
                    var cell = row.GetCell(addedColumnHeader);
                    var target = new RowIndexTarget(row.Index);
                    var value = new ConstantValue(cell);

                    if (cell != defaultCellValue)
                        values.Add(target, value);
                }

                modifiers.Add(new AddColumn2DAModifier(addedColumnHeader, defaultCellValue, values, new()));
            }

            for (int i = Older.Rows().Count; i < Newer.Rows().Count; i++)
            {
                var row = Newer.Row(i);

                var rowLabelValue = new ConstantValue(i.ToString());
                var cellValues = new Dictionary<string, IValue>();
                foreach (var columnHeader in Newer.ColumnHeaders())
                {
                    var cell = row.GetCell(columnHeader);
                    cellValues.Add(columnHeader, new ConstantValue(cell));
                }

                modifiers.Add(new AddRow2DAModifier(null, rowLabelValue, cellValues, new()));
            }

            return modifiers;
        }

        public bool IsSame()
        {
            var oldColumnHeaders = new HashSet<string>(Older.ColumnHeaders());
            var newColumnHeaders = new HashSet<string>(Newer.ColumnHeaders());

            if (!oldColumnHeaders.SetEquals(newColumnHeaders))
            {
                return false;
            }

            if (Older.Rows().Count != Newer.Rows().Count)
            {
                return false;
            }

            foreach (var oldRow in Older.Rows())
            {
                var newRow = Newer.Row(oldRow.Index);

                foreach (var columnHeader in Older.ColumnHeaders())
                {
                    var oldValue = oldRow.GetCell(columnHeader);
                    var newValue = newRow.GetCell(columnHeader);

                    if (oldValue != newValue)
                    {
                        return false;
                    }
                }
            }

            return true;
        }
    }
}
