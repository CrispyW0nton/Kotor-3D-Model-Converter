using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorTXI
{
    public class TXIWriter : IWriter<TXI>
    {
        public BinaryWriter? _writer;
        public TXI? _txi;

        public TXIWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public TXIWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(TXI value)
        {
            throw new NotImplementedException();
        }
    }
}
