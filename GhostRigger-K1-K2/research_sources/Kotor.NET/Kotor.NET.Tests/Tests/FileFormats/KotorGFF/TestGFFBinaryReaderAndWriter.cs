using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Formats.KotorGFF;
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tests.Tests.FileFormats.KotorGFF
{
    [TestClass]
    public class TestGFFBinaryReaderAndWriter
    {
        [TestMethod]
        public void ReadAndWrite()
        {
            var data = File.ReadAllBytes("./Files/test.gff");
            var gff = AssertRead(data);

            // Now that it has been confirmed that files are read correctly, the
            // file data will be written then that will be read to confirm that
            // the write was done correctly.
            var stream = new MemoryStream();
            var writer = new GFFBinaryWriter(stream);
            writer.Write(gff);
            AssertRead(stream.ToArray());
        }

        public GFF AssertRead(byte[] data)
        {
            var reader = new GFFBinaryReader(data);
            var gff = reader.Read();

            Assert.AreEqual(255, gff.Root.Get<byte>("uint8"));
            Assert.AreEqual(-128, gff.Root.Get<sbyte>("int8"));

            Assert.AreEqual(65535, gff.Root.Get<ushort>("uint16"));
            Assert.AreEqual(-32768, gff.Root.Get<short>("int16"));

            Assert.AreEqual(4294967295, gff.Root.Get<uint>("uint32"));
            Assert.AreEqual(-2147483648, gff.Root.Get<int>("int32"));

            Assert.AreEqual((ulong)4294967296, gff.Root.Get<ulong>("uint64"));
            Assert.AreEqual((long)2147483647, gff.Root.Get<long>("int64"));

            Assert.AreEqual(12.3456697463989f, gff.Root.Get<float>("single"));
            Assert.AreEqual(12.345678901234, gff.Root.Get<double>("double"));

            Assert.AreEqual("abcdefghij123456789", gff.Root.Get<string>("string"));
            Assert.AreEqual("resref01", gff.Root.Get<ResRef>("resref")!.Get());

            Assert.AreEqual(11, gff.Root.Get<Vector3>("position").X);
            Assert.AreEqual(22, gff.Root.Get<Vector3>("position").Y);
            Assert.AreEqual(33, gff.Root.Get<Vector3>("position").Z);

            Assert.AreEqual(1, gff.Root.Get<Vector4>("orientation").X);
            Assert.AreEqual(2, gff.Root.Get<Vector4>("orientation").Y);
            Assert.AreEqual(3, gff.Root.Get<Vector4>("orientation").Z);
            Assert.AreEqual(4, gff.Root.Get<Vector4>("orientation").W);

            var locstring = gff.Root.Get<LocalizedString>("locstring")!;
            Assert.AreEqual(-1, locstring.StringRef);
            Assert.AreEqual("male_eng", locstring.Get(Language.ENGLISH, Gender.MALE)!.Text);
            Assert.AreEqual("fem_german", locstring.Get(Language.GERMAN, Gender.FEMALE)!.Text);

            Assert.AreEqual(2, gff.Root.Get<GFFList>("list")!.Count);
            Assert.AreEqual(1u, gff.Root.Get<GFFList>("list")!.ElementAt(0).ID);
            Assert.AreEqual(2u, gff.Root.Get<GFFList>("list")!.ElementAt(1).ID);

            var childStruct = gff.Root.Get<GFFStruct>("child_struct");
            Assert.AreEqual(0u, childStruct!.ID);
            Assert.AreEqual(4, childStruct!.Get<byte>("child_uint8"));

            return gff;
        }
    }
}
