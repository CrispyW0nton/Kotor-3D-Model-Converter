using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Formats.KotorTLK
{
    public class TLK
    {
        public Language Language { get; set; }
        public List<TalkTableEntry> Entries { get; set; }

        public TLK()
        {
            Language = Language.ENGLISH;
            Entries = new();
        }
        public TLK(Language language)
        {
            Language = language;
            Entries = new();
        }

        public void Add(string text)
        {
            Entries.Add(new TalkTableEntry(text));
        }
        public void Add(string text, ResRef resref)
        {
            Entries.Add(new TalkTableEntry(text, resref));
        }

        public TalkTableEntry Get(int index)
        {
            return Entries[index];
        }
    }
}
