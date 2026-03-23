using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Formats.KotorTLK;

namespace Kotor.NET.Tests.Tests.Common
{
    [TestClass]
    public class TestTalkTable
    {
        private TalkTable _talkTable; 

        [TestInitialize]
        public void Init()
        {
            _talkTable = new TalkTable("./Files/test.tlk");
        }

        [TestMethod]
        public void Get_IsCorrect()
        {
            // Check the first entry is correct
            Assert.AreEqual("abcdef", _talkTable.Get(0).Text);
            Assert.AreEqual("resref01", _talkTable.Get(0).ResRef.Get());
            // Check the second entry is correct
            Assert.AreEqual("ghijklmnop", _talkTable.Get(1).Text);
            Assert.AreEqual("resref02", _talkTable.Get(1).ResRef.Get());
            // Check the third entry is correct
            Assert.AreEqual("qrstuvwxyz", _talkTable.Get(2).Text);
            Assert.AreEqual("", _talkTable.Get(2).ResRef.Get());
        }

        public void Language_IsCorrect()
        {
            // Check the language is correct
            Assert.AreEqual(Language.ENGLISH, _talkTable.Language());
        }

        public void Size_IsCorrect()
        {
            // Check there are the correct number of entries
            Assert.AreEqual(3, _talkTable.Size());
        }
    }
}
