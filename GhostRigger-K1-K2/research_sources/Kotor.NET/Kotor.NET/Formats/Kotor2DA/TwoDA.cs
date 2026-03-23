using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.Kotor2DA
{
    /// <summary>
    /// Represents the table data structure of the 2DA file format used by
    /// the KotOR game engine.
    /// </summary>
    public class TwoDA
    {
        internal List<string> _headers { get; set; }
        internal List<TwoDARow> _rows { get; set; }

        public TwoDA()
        {
            _headers = new List<string>();
            _rows = new List<TwoDARow>();
        }

        /// <summary>
        /// Returns a list of all rows in the table.
        /// </summary>
        /// <returns>Every row.</returns>
        public IReadOnlyList<TwoDARow> Rows()
        {
            return _rows.AsReadOnly();
        }

        /// <summary>
        /// Returns the row at the given index or null if it does not exist.
        /// </summary>
        /// <param name="rowIndex">The index of the target row.</param>
        /// <returns>A row at the given index or null if it does not exist.</returns>
        public TwoDARow? Row(int rowIndex)
        {
            return Rows().ElementAtOrDefault(rowIndex);
        }

        /// <summary>
        /// Returns the row at with the given row header or null if it could not be found.
        /// </summary>
        /// <param name="rowHeader">The header of the target row.</param>
        /// <returns>A row with the given header or null if it could not be found.</returns>
        public TwoDARow? Row(string rowHeader)
        {
            return Rows().SingleOrDefault(x => x.Header == rowHeader);
        }

        /// <summary>
        /// Adds an empty new row to the bottom of the table.
        /// </summary>
        /// <param name="header">The header of the new row.</param>
        /// <returns>The new row.</returns>
        public TwoDARow AddRow(string header)
        {
            var row = new TwoDARow(this, header);
            _rows.Add(row);
            return row;
        }

        /// <summary>
        /// Removes the row at the given index.
        /// </summary>
        /// <param name="index">The index of the target row.</param>
        public void RemoveRow(int index)
        {
            _rows.RemoveAt(index);
        }

        /// <summary>
        /// Removes the row with the given row header.
        /// </summary>
        /// <param name="header">The header of the target row.</param>
        public void RemoveRow(string header)
        {
            var matchingRows = _rows.Where(x => x.Header == header);
            foreach (var row in matchingRows)
            {
                _rows.Remove(row);
            }
        }

        /// <summary>
        /// Returns a list of all column headers.
        /// </summary>
        /// <returns>All column headers.</returns>
        public IReadOnlyList<string> ColumnHeaders()
        {
            return _headers.AsReadOnly();
        }

        /// <summary>
        /// Adds a new column to the table.
        /// </summary>
        /// <param name="header">The header of the new column.</param>
        public void AddColumn(string header)
        {
            _headers.Add(header);
        }

        /// <summary>
        /// Removes a column with the given column header.
        /// </summary>
        /// <param name="header">The header of the target column.</param>
        public void RemoveColumn(string header)
        {
            _headers.Remove(header);
        }

        /// <summary>
        /// Returns a list of cell values under a given column. The list is ordered from
        /// the start of the table (index 0) to the end of the table.
        /// </summary>
        /// <param name="header">The header of the target column.</param>
        /// <returns>A list of cell values.</returns>
        public IReadOnlyList<string> GetCellsUnderColumn(string header)
        {
            var cells = new List<string>();

            foreach (var row in _rows)
            {
                cells.Add(row.GetCell(header));
            }

            return cells.AsReadOnly();
        }

        /// <summary>
        /// Shrinks or expands the table to the given number of rows.
        /// </summary>
        /// <param name="size">How many rows the table should have.</param>
        /// <exception cref="ArgumentOutOfRangeException">A size smaller than 0
        /// was specified.</exception>
        public void Resize(int size)
        {
            if (size < 0)
            {
                throw new ArgumentOutOfRangeException();
            }

            if (size < _rows.Count)
            {
                _rows.RemoveRange(size, _rows.Count - size);
            }
            else
            {
                for (int i = 0; i < size - _rows.Count; i++)
                {
                    AddRow(i.ToString());
                }
            }
        }
    }

    /// <summary>
    /// Stores the data of a 2DA row.
    /// </summary>
    public class TwoDARow
    {
        /// <summary>
        /// The row header text.
        /// </summary>
        public string Header { get; set; }
        /// <summary>
        /// The index of the row.
        /// </summary>
        public int Index { get => _twoda.Rows().ToList().IndexOf(this); }

        private TwoDA _twoda;
        private Dictionary<string, string> _cells;

        internal TwoDARow(TwoDA twoda, string label)
        {
            Header = label;
            _twoda = twoda;
            _cells = new Dictionary<string, string>();
        }

        /// <summary>
        /// Gets the value of a cell under the given column.
        /// </summary>
        /// <param name="columnHeader">The header of the target column.</param>
        /// <returns>The value of a cell.</returns>
        public string? GetCell(string columnHeader)
        {
            return _cells.ContainsKey(columnHeader) ? _cells[columnHeader] : null;
        }

        /// <summary>
        /// Sets the value of a cell under the given column.
        /// </summary>
        /// <param name="columnHeader">The header of the target column.</param>
        /// <param name="cellValue">The new cell value.</param>
        public void SetCell(string columnHeader, string cellValue)
        {
            _cells[columnHeader] = cellValue;
        }
    }
}
