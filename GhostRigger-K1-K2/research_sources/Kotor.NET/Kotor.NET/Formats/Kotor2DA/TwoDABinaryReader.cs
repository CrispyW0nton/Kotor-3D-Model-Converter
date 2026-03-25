using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using static Kotor.NET.Formats.Kotor2DA.TwoDABinaryStructure;

namespace Kotor.NET.Formats.Kotor2DA
{
    public class TwoDABinaryReader : IReader<TwoDA>
    {
        private BinaryReader _reader;
        private TwoDA? _twoda;

        private readonly string[] _validFileTypes = new[] { "2DA ", };
        private readonly string _validFileVersion = "V1.0";

        public TwoDABinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public TwoDABinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }

        public TwoDABinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public TwoDA Read()
        {
            _twoda = new TwoDA();

            var file = new FileRoot(_reader);

            foreach (var header in file.ColumnHeaders)
            {
                _twoda.AddColumn(header);
            }

            var columnCount = file.ColumnHeaders.Count;
            for (int i = 0; i < file.RowHeaders.Count; i++)
            {
                var label = file.RowHeaders[i];
                var row = _twoda.AddRow(label);

                for (int j = 0; j < file.ColumnHeaders.Count; j++)
                {
                    var header = file.ColumnHeaders[j];
                    var cellIndex = i * file.RowHeaders.Count + j;
                    var cell = file.CellValues[cellIndex];
                    row.SetCell(header, cell);
                }
            }

            return _twoda;
        }
    }
}
