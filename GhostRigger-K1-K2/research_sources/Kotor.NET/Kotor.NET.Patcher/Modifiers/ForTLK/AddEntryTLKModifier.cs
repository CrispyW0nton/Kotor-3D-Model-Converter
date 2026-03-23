using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorTLK;

namespace Kotor.NET.Patcher.Modifiers.ForTLK
{
    public class AddEntryTLKModifier : IModifier<TLK>
    {
        public string Text { get; set; }
        public ResRef SoundResRef { get ; set; }
        public int MemoryTokenID { get; set; }

        public AddEntryTLKModifier(string text, ResRef soundResRef, int memoryTokenID)
        {
            Text = text;
            SoundResRef = soundResRef;
            MemoryTokenID = memoryTokenID;
        }

        public void Apply(TLK target, IMemory memory, ILogger logger)
        {
            target.Add(Text, SoundResRef);
            memory.SetTLKToken(MemoryTokenID, target.Entries.Count);
        }
    }
}
