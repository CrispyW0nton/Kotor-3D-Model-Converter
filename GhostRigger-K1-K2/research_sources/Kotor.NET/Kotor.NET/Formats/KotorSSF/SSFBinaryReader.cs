using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorTLK;
using static Kotor.NET.Formats.KotorSSF.SSFBinaryStructure;

namespace Kotor.NET.Formats.KotorSSF
{
    public class SSFBinaryReader : IReader<SSF>
    {
        private BinaryReader _reader;
        private SSF? _ssf;

        public SSFBinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public SSFBinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public SSFBinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public SSF Read()
        {
            var root = new FileRoot(_reader);

            _ssf = new SSF();

            for (int i = 0; i <= 27; i++)
            {
                var sound = (CreatureSound)i;
                var stringref = root.SoundTable.SoundStringRefs[i];
                _ssf.Set(sound, stringref);
            }

            return _ssf;
        }
    }
}
