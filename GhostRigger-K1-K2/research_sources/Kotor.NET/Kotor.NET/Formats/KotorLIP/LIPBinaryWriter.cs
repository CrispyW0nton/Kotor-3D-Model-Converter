using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorLIP
{
    public class LIPBinaryWriter : IWriter<LIP>
    {
        public BinaryWriter? _writer;
        public TwoDA? _twoda;

        public LIPBinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public LIPBinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(LIP value)
        {
            throw new NotImplementedException();
        }
    }
}
