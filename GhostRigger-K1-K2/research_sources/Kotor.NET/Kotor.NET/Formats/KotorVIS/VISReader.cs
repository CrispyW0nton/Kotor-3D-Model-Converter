using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorVIS
{
    public class VISReader : IReader<VIS>
    {
        private BinaryReader _reader;
        private VIS? _vis;

        public VISReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public VISReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }

        public VISReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public VIS Read()
        {
            throw new NotImplementedException();
        }
    }
}
