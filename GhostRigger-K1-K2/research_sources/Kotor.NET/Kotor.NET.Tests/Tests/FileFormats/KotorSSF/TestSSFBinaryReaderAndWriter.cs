using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorSSF;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;

namespace Kotor.NET.Tests.Tests.FileFormats.KotorSSF
{
    [TestClass]
    public class TestSSFBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            var data = File.ReadAllBytes("./Files/test.ssf");
            var ssf = AssertRead(data);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            var stream = new MemoryStream();
            var writer = new SSFBinaryWriter(stream);
            writer.Write(ssf);
            AssertRead(stream.ToArray());
        }

        public SSF AssertRead(byte[] data)
        {
            var reader = new SSFBinaryReader(data);
            var ssf = reader.Read();

            Assert.AreEqual(123075, ssf.Get((CreatureSound)0));
            Assert.AreEqual(123074, ssf.Get((CreatureSound)1));
            Assert.AreEqual(123073, ssf.Get((CreatureSound)2));
            Assert.AreEqual(123072, ssf.Get((CreatureSound)3));
            Assert.AreEqual(123071, ssf.Get((CreatureSound)4));
            Assert.AreEqual(123070, ssf.Get((CreatureSound)5));
            Assert.AreEqual(123069, ssf.Get((CreatureSound)6));
            Assert.AreEqual(123068, ssf.Get((CreatureSound)7));
            Assert.AreEqual(123067, ssf.Get((CreatureSound)8));
            Assert.AreEqual(123066, ssf.Get((CreatureSound)9));
            Assert.AreEqual(123065, ssf.Get((CreatureSound)10));
            Assert.AreEqual(123064, ssf.Get((CreatureSound)11));
            Assert.AreEqual(123063, ssf.Get((CreatureSound)12));
            Assert.AreEqual(123062, ssf.Get((CreatureSound)13));
            Assert.AreEqual(123061, ssf.Get((CreatureSound)14));
            Assert.AreEqual(123060, ssf.Get((CreatureSound)15));
            Assert.AreEqual(123059, ssf.Get((CreatureSound)16));
            Assert.AreEqual(123058, ssf.Get((CreatureSound)17));
            Assert.AreEqual(123057, ssf.Get((CreatureSound)18));
            Assert.AreEqual(123056, ssf.Get((CreatureSound)19));
            Assert.AreEqual(123055, ssf.Get((CreatureSound)20));
            Assert.AreEqual(123054, ssf.Get((CreatureSound)21));
            Assert.AreEqual(123053, ssf.Get((CreatureSound)22));
            Assert.AreEqual(123052, ssf.Get((CreatureSound)23));
            Assert.AreEqual(123051, ssf.Get((CreatureSound)24));
            Assert.AreEqual(123050, ssf.Get((CreatureSound)25));
            Assert.AreEqual(123049, ssf.Get((CreatureSound)26));
            Assert.AreEqual(123048, ssf.Get((CreatureSound)27));

            return ssf;
        }
    }
}
