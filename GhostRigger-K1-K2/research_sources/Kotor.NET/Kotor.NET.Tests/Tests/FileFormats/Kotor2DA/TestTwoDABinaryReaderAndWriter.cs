using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tests.Tests.FileFormats.Kotor2DA
{
    [TestClass]
    public class TestGFFBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            var data = File.ReadAllBytes("./Files/test.2da");
            var twoda = AssertRead(data);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            var stream = new MemoryStream();
            var writer = new TwoDABinaryWriter(stream);
            writer.Write(twoda);
            AssertRead(stream.ToArray());
        }

        public TwoDA AssertRead(byte[] data)
        {
            // | col3 | col2 | col1 |
            // ----------------------
            // | ghi  | def  | abc  |
            // | 123  | ghi  | def  |
            // | abc  |      | 123  |

            var reader = new TwoDABinaryReader(data);
            var twoda = reader.Read();

            // The columns are correct
            Assert.AreEqual("col3", twoda.ColumnHeaders().ElementAt(0));
            Assert.AreEqual("col2", twoda.ColumnHeaders().ElementAt(1));
            Assert.AreEqual("col1", twoda.ColumnHeaders().ElementAt(2));
            // The first row is correct
            Assert.AreEqual("ghi", twoda.Row(0).GetCell("col3"));
            Assert.AreEqual("def", twoda.Row(0).GetCell("col2"));
            Assert.AreEqual("abc", twoda.Row(0).GetCell("col1"));
            // The second row is correct
            Assert.AreEqual("123", twoda.Row(1).GetCell("col3"));
            Assert.AreEqual("ghi", twoda.Row(1).GetCell("col2"));
            Assert.AreEqual("def", twoda.Row(1).GetCell("col1"));
            // The third row is correct
            Assert.AreEqual("abc", twoda.Row(2).GetCell("col3"));
            Assert.AreEqual("",    twoda.Row(2).GetCell("col2"));
            Assert.AreEqual("123", twoda.Row(2).GetCell("col1"));

            return twoda;
        }
    }
}
