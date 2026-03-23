using Kotor.NET.Common.Data;

namespace Kotor.NET.Common
{
    public class TalkTableEntry
    {
        public string Text { get; set; }
        public ResRef ResRef { get; set; }

        public TalkTableEntry(string text, ResRef resRef)
        {
            Text = text;
            ResRef = resRef;
        }

        public TalkTableEntry(string text)
        {
            Text = text;
            ResRef = new();
        }
    }
}
