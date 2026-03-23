using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorERF;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tests.Tests.FileFormats.KotorERF
{
    [TestClass]
    public class TestERFBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            var data = File.ReadAllBytes("./Files/test.erf");
            var erf = AssertRead(data);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            var stream = new MemoryStream();
            var writer = new ERFBinaryWriter(stream);
            writer.Write(erf);
            AssertRead(stream.ToArray());
        }

        public ERF AssertRead(byte[] data)
        {
            // | ResRef | ResType | Data |
            // ----------------------
            // | npc    | utc     | 'a'  |
            // | door   | utd     | 'b'  |
            // | sword  | uti     | 'c'  |

            var reader = new ERFBinaryReader(data);
            var erf = reader.Read();

            // Check 'npc.utc'
            var res1 = erf.Get("npc", ResourceType.UTC);
            Assert.IsNotNull(res1);
            Assert.IsTrue(new byte[] { 97 }.SequenceEqual(res1.Data));

            // Check 'door.utd'
            var res2 = erf.Get("door", ResourceType.UTD);
            Assert.IsNotNull(res2);
            Assert.IsTrue(new byte[] { 98 }.SequenceEqual(res2.Data));

            // Check 'sword.uti'
            var res3 = erf.Get("sword", ResourceType.UTI);
            Assert.IsNotNull(res3);
            Assert.IsTrue(new byte[] { 99 }.SequenceEqual(res3.Data));

            return erf;
        }
    }
}
