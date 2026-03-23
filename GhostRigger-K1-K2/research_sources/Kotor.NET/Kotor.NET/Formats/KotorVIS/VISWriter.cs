using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorVIS
{
    public class VISWriter : IWriter<VIS>
    {
        public BinaryWriter? _writer;
        public VIS? _vis;

        public VISWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public VISWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(VIS value)
        {
            throw new NotImplementedException();
        }
    }
}
