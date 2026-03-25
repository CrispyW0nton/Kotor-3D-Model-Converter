using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorLYT
{
    public class LYTWriter : IWriter<LYT>
    {
        public BinaryWriter? _writer;
        public TwoDA? _twoda;

        public LYTWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public LYTWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(LYT value)
        {
            throw new NotImplementedException();
        }
    }
}
