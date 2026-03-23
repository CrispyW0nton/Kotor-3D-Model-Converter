using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Formats.KotorMDL;
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tests.Tests.FileFormats.KotorMDL
{
    [TestClass]
    public class TestMDLBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            //var memoryStream = new MemoryStream();
            //var binaryWriter = new BinaryWriter(memoryStream);
            //binaryWriter.BaseStream.Position = 10;
            //binaryWriter.Write((byte)1);
            //var bytes = memoryStream.ToArray();

            var path = @"C:\Users\hugin\Desktop\ext\p_t3m3";

            var data = File.ReadAllBytes($"{path}.mdl");
            var mdxData = File.ReadAllBytes($"{path}.mdx");
            var mdl = AssertRead(data, mdxData);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            //var stream = new MemoryStream();
            //var writer = new BinaryWriter(stream);
            //writer.Write(mdl);
            //AssertRead(stream.ToArray());
        }

        public MDL AssertRead(byte[] data, byte[] mdxData)
        {

            var reader = new MDLBinaryReader(data, mdxData);
            var mdl = reader.Read();

            var writer = new MDLBinaryWriter();
            data = writer.Bytes(mdl);
            using (var memoryStream = new MemoryStream((int)writer.MDXStream.Length))
            {
                writer.MDXStream.Position = 0;
                writer.MDXStream.CopyTo(memoryStream);
                mdxData = memoryStream.ToArray();
            }

            var path = @"C:\Program Files (x86)\Steam\steamapps\common\swkotor\Override\p_t3m3";
            File.WriteAllBytes($"{path}.mdl", data);
            File.WriteAllBytes($"{path}.mdx", mdxData);
            reader = new MDLBinaryReader(data, mdxData);
            mdl = reader.Read();

            return mdl;
        }
    }
}
