using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorRIM;

namespace Kotor.NET.Tests.Tests.FileFormats.KotorRIM
{
    [TestClass]
    public class TestRIMBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            var data = File.ReadAllBytes("./Files/test.rim");
            var rim = AssertRead(data);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            var stream = new MemoryStream();
            var writer = new RIMBinaryWriter(stream);
            writer.Write(rim);
            AssertRead(stream.ToArray());
        }

        public RIM AssertRead(byte[] data)
        {
            // | ResRef | ResType | Data |
            // ----------------------
            // | npc    | utc     | 'a'  |
            // | door   | utd     | 'b'  |
            // | sword  | uti     | 'c'  |

            var reader = new RIMBinaryReader(data);
            var rim = reader.Read();

            // Check 'npc.utc'
            var res1 = rim.Get("npc", ResourceType.UTC);
            Assert.IsNotNull(res1);
            Assert.IsTrue(new byte[] { 97 }.SequenceEqual(res1.Data));

            // Check 'door.utd'
            var res2 = rim.Get("door", ResourceType.UTD);
            Assert.IsNotNull(res2);
            Assert.IsTrue(new byte[] { 98 }.SequenceEqual(res2.Data));

            // Check 'sword.uti'
            var res3 = rim.Get("sword", ResourceType.UTI);
            Assert.IsNotNull(res3);
            Assert.IsTrue(new byte[] { 99 }.SequenceEqual(res3.Data));

            return rim;
        }
    }
}
