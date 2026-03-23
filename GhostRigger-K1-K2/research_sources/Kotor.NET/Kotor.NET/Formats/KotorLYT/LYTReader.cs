using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorLYT
{
    public class LYTReader : IReader<LYT>
    {
        private BinaryReader _reader;
        private TwoDA? _twoda;

        public LYTReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public LYTReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }

        public LYT Read()
        {
            throw new NotImplementedException();
        }
    }
}
