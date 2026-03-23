using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorNCS
{
    public class NCSReader : IReader<NCS>
    {
        private BinaryReader _reader;
        private TwoDA? _twoda;

        public NCSReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public NCSReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }

        public NCS Read()
        {
            throw new NotImplementedException();
        }
    }
}
