using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Formats.KotorNCS
{
    public class NCSWriter : IWriter<NCS>
    {
        public BinaryWriter? _writer;
        public NCS? _ncs;

        public NCSWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public NCSWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(NCS value)
        {
            throw new NotImplementedException();
        }
    }
}
