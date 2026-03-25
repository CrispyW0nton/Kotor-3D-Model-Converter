using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;
using static Kotor.NET.Formats.KotorERF.ERFBinaryStructure;

namespace Kotor.NET.Formats.KotorERF
{
    public class ERFBinaryReader : IReader<ERF>
    {
        private BinaryReader _reader;
        private ERF _erf = new();

        public ERFBinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public ERFBinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public ERFBinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public ERF Read()
        {
            _erf = new ERF();

            var root = new FileRoot(_reader);

            for (int i = 0; i < root.KeyEntries.Count; i ++)
            {
                var key = root.KeyEntries[i];
                var resource = root.ResourceEntries[i];
                var data = root.ResourceData[i];

                _erf.Resources.Add(new Resource(key.ResRef, ResourceType.ByID(key.ResType), data));
            }

            return _erf;
        }
    }
}
