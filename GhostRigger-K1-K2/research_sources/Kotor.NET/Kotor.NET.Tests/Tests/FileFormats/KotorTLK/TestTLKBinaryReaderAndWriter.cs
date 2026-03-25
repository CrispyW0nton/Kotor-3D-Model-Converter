using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorTLK;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;

namespace Kotor.NET.Tests.Tests.FileFormats.KotorTLK
{
    [TestClass]
    public class TestTLKBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            var data = File.ReadAllBytes("./Files/test.tlk");
            var gff = AssertRead(data);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            var stream = new MemoryStream();
            var writer = new TLKBinaryWriter(stream);
            writer.Write(gff);
            AssertRead(stream.ToArray());
        }

        public TLK AssertRead(byte[] data)
        {
            //   | Text          | Sound    |
            // --|---------------------------
            // 0 | abcdef        | resref01 |
            // 1 | ghijklmnop    | resref02 |
            // 2 | qrstuvwxyz    |          |
            // --|---------------|----------|

            var reader = new TLKBinaryReader(data);
            var tlk = reader.Read();

            // Check the language is correct
            Assert.AreEqual(Language.ENGLISH, tlk.Language);
            // Check there are the correct number of entries
            Assert.AreEqual(3, tlk.Entries.Count);
            // Check the first entry is correct
            Assert.AreEqual("abcdef",   tlk.Get(0).Text);
            Assert.AreEqual("resref01", tlk.Get(0).ResRef.Get());
            // Check the second entry is correct
            Assert.AreEqual("ghijklmnop", tlk.Get(1).Text);
            Assert.AreEqual("resref02",   tlk.Get(1).ResRef.Get());
            // Check the third entry is correct
            Assert.AreEqual("qrstuvwxyz", tlk.Get(2).Text);
            Assert.AreEqual("",           tlk.Get(2).ResRef.Get());

            return tlk;
        }
    }
}
