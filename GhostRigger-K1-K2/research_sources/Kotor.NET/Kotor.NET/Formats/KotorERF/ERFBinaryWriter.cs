using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using static Kotor.NET.Formats.KotorERF.ERFBinaryStructure;

namespace Kotor.NET.Formats.KotorERF
{
    public class ERFBinaryWriter : IWriter<ERF>
    {
        public BinaryWriter _writer;
        public ERF _erf = new();

        public ERFBinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public ERFBinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(ERF erf)
        {
            _erf = erf;
            var file = Build();
            file.Write(_writer);
        }

        private FileRoot Build()
        {
            var root = new FileRoot();

            var erfTypeString = new Dictionary<ERFType, string>
            {
                [ERFType.ERF] = "ERF ",
                [ERFType.MOD] = "MOD ",
                [ERFType.SAV] = "SAV ",
            };

            var keyListOffset = FileHeader.SIZE;
            var resourceListOffset = keyListOffset + (KeyEntry.SIZE * _erf.Resources.Count);
            var resourceDataOffset = resourceListOffset + (ResourceEntry.SIZE * _erf.Resources.Count);

            root.FileHeader = new FileHeader
            {
                FileType = erfTypeString[_erf.Type],
                FileVersion = "V1.0",
                EntryCount = _erf.Resources.Count,
                OffsetToKeyList = keyListOffset,
                OffsetToResourceList = resourceListOffset,
                BuildYear = DateTime.Now.Year,
                BuildDay = DateTime.Now.Day,
            };
            
            for (int i = 0; i < _erf.Resources.Count; i++)
            {
                var resource = _erf.Resources[i];

                root.KeyEntries.Add(new KeyEntry
                {
                    ResRef = resource.ResRef,
                    ResType = (ushort)resource.Type.ID,
                    ResID = (uint)i,
                });

                root.ResourceEntries.Add(new ResourceEntry
                {
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
