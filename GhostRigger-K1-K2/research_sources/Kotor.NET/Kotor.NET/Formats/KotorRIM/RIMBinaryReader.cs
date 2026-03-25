using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorERF;
using static Kotor.NET.Formats.KotorRIM.RIMBinaryStructure;

namespace Kotor.NET.Formats.KotorRIM
{
    public class RIMBinaryReader : IReader<RIM>
    {
        public BinaryReader _reader;
        public RIM _rim = new();

        public RIMBinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public RIMBinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public RIMBinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public RIM Read()
        {
            _rim = new RIM();

            var root = new FileRoot(_reader);

            for (int i = 0; i < root.ResourceEntries.Count; i++)
            {
                var resource = root.ResourceEntries[i];
                var data = root.ResourceData[i];

                _rim.Resources.Add(new Resource(resource.ResRef, ResourceType.ByID(resource.ResourceTypeID), data));
            }

            return _rim;
        }
    }
}
