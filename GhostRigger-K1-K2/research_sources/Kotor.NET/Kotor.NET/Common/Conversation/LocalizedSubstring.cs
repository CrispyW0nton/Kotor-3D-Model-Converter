using Kotor.NET.Common.Creature;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Conversation
{
    public class LocalizedSubstring
    {
        public Language Language { get; set; }
        public Gender Gender { get; set; }
        public string Text { get; set; }

        public LocalizedSubstring(Language language, Gender gender, string text)
        {
            Language = language;
            Gender = gender;
            Text = text;
        }
    }
}
