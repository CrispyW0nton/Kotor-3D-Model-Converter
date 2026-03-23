using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Conversation
{
    /// <summary>
    /// A specialized string class designed around letting players see string's
    /// in their own language.
    /// </summary>
    public class LocalizedString
    {
        /// <summary>
        /// Index into the dialog.tlk file which contains the text localized to
        /// the player's specific language. If this value is set to -1 then the
        /// substrings are to be used instead.
        /// </summary>
        public int StringRef { get; set; }
        /// <summary>
        /// Each substring stores its own text linked to a specific language and
        /// gender.
        /// </summary>
        public List<LocalizedSubstring> Substrings { get; set; } = new();

        public LocalizedString()
        {
            StringRef = -1;
        }

        public LocalizedString(int stringref)
        {
            StringRef = stringref;
        }

        public LocalizedString(string englishSubstring)
        {
            Set(Language.ENGLISH, Gender.MALE, englishSubstring);
        }

        /// <summary>
        /// Returns a substring with the specified language and gender. If it does
        /// not exist then null is returned instead.
        /// </summary>
        /// <param name="language">The language of the substring.</param>
        /// <param name="gender">The gender of the substring.</param>
        /// <returns>The desired substring or null if it does not exist.</returns>
        public LocalizedSubstring? Get(Language language, Gender gender)
        {
            return Substrings.SingleOrDefault(x => x.Language == language && x.Gender == gender);
        }

        /// <summary>
        /// Sets a substring of the specified language and gender with the given
        /// text. If a substring matching the language and gender already exists
        /// then it is removed and replaced.
        /// </summary>
        /// <param name="language">The language of the new substring.</param>
        /// <param name="gender">The gender of the new substring.</param>
        /// <param name="text"\>The text of the new substring.</param>
        public void Set(Language language, Gender gender, string text)
        {
            var substring = new LocalizedSubstring(language, gender, text);

            // Avoid duplicate substrings of the same language/gender
            Substrings = Substrings.Where(x => x.Language != language && x.Gender != gender).ToList();

            Substrings.Add(substring);
        }

        public void Set(int substringID, string text)
        {
            var language = (Language)(substringID / 2);
            var gender = (Gender)(substringID % 2);
            var substring = new LocalizedSubstring(language, gender, text);

            // Avoid duplicate substrings of the same language/gender
            Substrings = Substrings.Where(x => x.Language != language && x.Gender != gender).ToList();

            Substrings.Add(substring);
        }

        public static implicit operator LocalizedString(int stringref)
        {
            return new LocalizedString(stringref);
        }
    }
}
