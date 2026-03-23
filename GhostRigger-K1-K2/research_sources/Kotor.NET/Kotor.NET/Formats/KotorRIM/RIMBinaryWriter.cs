using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorERF;
using static Kotor.NET.Formats.KotorRIM.RIMBinaryStructure;

namespace Kotor.NET.Formats.KotorRIM
{
    public class RIMBinaryWriter : IWriter<RIM>
    {
        public Stream Stream => _writer.BaseStream;

        private BinaryWriter _writer;
        private RIM _rim = new();

        public RIMBinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public RIMBinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }
        public RIMBinaryWriter()
        {
            var stream = new MemoryStream();
            _writer = new BinaryWriter(stream);
        }

        public byte[] Bytes(RIM rim)
        {
            using (var memoryStream = new MemoryStream())
            {
                Write(rim);
                Stream.CopyTo(memoryStream);
                return memoryStream.ToArray();
            }
        }

        public void Write(RIM rim)
        {
            _rim = rim;
            var file = Build();
            file.Write(_writer);
        }

        private FileRoot Build()
        {
            var root = new FileRoot();

            var resourceListOffset = FileHeader.SIZE;
            var resourceDataOffset = resourceListOffset + (ResourceEntry.SIZE * _rim.Resources.Count);

            root.FileHeader = new FileHeader
            {
                FileType = "RIM ",
                FileVersion = "V1.0",
                ResourceCount = _rim.Resources.Count,
                OffsetToResources = resourceListOffset,
            };

            for (int i = 0; i < _rim.Resources.Count; i++)
            {
                var resource = _rim.Resources[i];

                root.ResourceEntries.Add(new ResourceEntry
                {
                    ResRef = resource.ResRef,
                    ResourceTypeID = (ushort)resource.Type.ID,
                    ResourceID = i,
                    Offset = resourceDataOffset,
                    Size = resource.Data.Length,
                });

                root.ResourceData.Add(resource.Data);
                resourceDataOffset += resource.Data.Length;
            }

            return root;
        }
    }
}
