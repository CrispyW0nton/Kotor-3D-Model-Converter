using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorTXI
{
    public class TXIReader : IReader<TXI>
    {
        private BinaryReader _reader;
        private TXI? _txi;

        public TXIReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public TXIReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }

        public TXIReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public TXI Read()
        {
            throw new NotImplementedException();
        }
    }
}
