using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;

namespace Kotor.NET.Formats.KotorLIP
{
    public class BinaryLIPReader : IReader<LIP>
    {
        private BinaryReader _reader;
        private LIP? _twoda;

        public BinaryLIPReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public BinaryLIPReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }

        public BinaryLIPReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public LIP Read()
        {
            throw new NotImplementedException();
        }
    }
}
