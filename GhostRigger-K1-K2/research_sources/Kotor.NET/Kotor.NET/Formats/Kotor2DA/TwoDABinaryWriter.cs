using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using static Kotor.NET.Formats.Kotor2DA.TwoDABinaryStructure;

namespace Kotor.NET.Formats.Kotor2DA
{
    public class TwoDABinaryWriter : IWriter<TwoDA>
    {
        public BinaryWriter? _writer;
        public TwoDA? _twoda;

        public TwoDABinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public TwoDABinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(TwoDA twoda)
        {
            var root = new FileRoot();

            root.FileHeader.FileType = "2DA ";
            root.FileHeader.FileVersion = "v2.b";
            root.ColumnHeaders = twoda.ColumnHeaders().ToList();
            
            foreach (var row in twoda.Rows())
            {
                root.RowHeaders.Add(row.Header);
                
                var cells = twoda.ColumnHeaders().Select(x => row.GetCell(x)).ToList();
                root.CellValues.AddRange(cells);
            }

            root.Write(_writer);
        }
    }
}
