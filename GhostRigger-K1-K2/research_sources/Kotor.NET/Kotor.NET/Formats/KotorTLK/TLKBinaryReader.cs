using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;
using static Kotor.NET.Formats.KotorTLK.TLKBinaryStructure;

namespace Kotor.NET.Formats.KotorTLK
{
    public class TLKBinaryReader : IReader<TLK>
    {
        private BinaryReader _reader;
        private TLK? _tlk;

        public TLKBinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public TLKBinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public TLKBinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public TLK Read()
        {
            var root = new FileRoot(_reader);

            _tlk = new TLK();

            _tlk.Language = (Language)root.FileHeader.LanguageID;

            for (int i = 0; i < root.FileHeader.StringCount; i++)
            {
                var text = root.StringEntries[i];
                var resref = root.StringData[i].SoundResRef;
                _tlk.Add(text, resref);
            }

            return _tlk;
        }
    }
}
