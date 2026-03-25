using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Geometry;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Patching;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Patching.Parsers.LegacyINI;
using Moq.AutoMock;

namespace Kotor.NET.Tests.Tests.Patching.Parsers.LegacyINI
{
    [TestClass]
    public class TestGFF
    {
        IMemory memory;
        Logger logger;
        GFF gff;

        [TestInitialize]
        public void Init()
        {
            var mocker = new AutoMocker();

            memory = new Memory();
            logger = new Logger();
            gff = new GFF();

            // [List] Field_List
            //      [Struct] 0
            //      [Struct] 1
            // [Struct] Field_Struct
            //      [Int32] Field_C
            // [LocString] Field_LocString

            var fieldA = new GFFList();
            fieldA.Add(new());
            fieldA.Add(new());

            var fieldB = new GFFStruct();
            fieldB.Set("Field_C", 123);

            gff.Root.Set("Field_List", fieldA);
            gff.Root.Set("Field_Struct", fieldB);
            gff.Root.Set("Field_Int8", (sbyte)8);
            gff.Root.Set("Field_UInt8", (byte)8);
            gff.Root.Set("Field_Int16", (Int16)8);
            gff.Root.Set("Field_UInt16", (UInt16)8);
            gff.Root.Set("Field_Int32", (Int32)8);
            gff.Root.Set("Field_UInt32", (UInt32)8);
            gff.Root.Set("Field_Int64", (Int64)8);
            gff.Root.Set("Field_UInt64", (UInt64)8);
            gff.Root.Set("Field_Single", (Single)8);
            gff.Root.Set("Field_Double", (Double)8);
            gff.Root.Set("Field_String", "");
            gff.Root.Set("Field_ResRef", new ResRef(""));
            gff.Root.Set("Field_LocString", new LocalizedString(123));
            gff.Root.Set("Field_Vector3", new Vector3());
            gff.Root.Set("Field_Vector4", new Vector4());

            memory.Set2DAToken(1, "432");
            memory.SetTLKToken(1, 987);
        }

        [TestMethod]
        public void Modify_AllValueTypes()
        {
            var ini =
                """
                [GFFList]
                Table0=test.gff

                [test.gff]
                Field_Int8=-127
                Field_UInt8=127
                Field_Int16=-127
                Field_UInt16=127
                Field_Int32=-127
                Field_UInt32=127
                Field_Int64=-127
                Field_UInt64=127
                Field_Single=3.21
                Field_Double=1.23
                Field_String=abc
                Field_ResRef=-xyz
                Field_LocString(stringref)=222
                Field_Vector3=1.1|2.2|3.3
                Field_Vector4=1.1|2.2|3.3|4.4
                """;

            var data = new LegacyINIReader(ini).Parse();
            data.GFFFiles.First().Modifiers.ForEach(x => x.Apply(gff, memory, logger));

            Assert.AreEqual(-127, gff.Root.Get<SByte>("Field_Int8", 0));
            Assert.AreEqual(127, gff.Root.Get<Byte>("Field_UInt8", 0));
            Assert.AreEqual(-127, gff.Root.Get<Int16>("Field_Int16", 0));
            Assert.AreEqual(127, gff.Root.Get<UInt16>("Field_UInt16", 0));
            Assert.AreEqual(-127, gff.Root.Get<Int32>("Field_Int32", 0));
            Assert.AreEqual(127, gff.Root.Get<UInt32>("Field_UInt32", 0));
            Assert.AreEqual(-127, gff.Root.Get<Int64>("Field_Int64", 0));
            Assert.AreEqual(127, gff.Root.Get<UInt64>("Field_UInt64", 0));
            Assert.AreEqual(3.21, gff.Root.Get<Single>("Field_Single", 0));
            Assert.AreEqual(1.23, gff.Root.Get<Double>("Field_Double", 0));
            Assert.AreEqual("abc", gff.Root.Get<String>("Field_String", ""));
            Assert.AreEqual("xyz", gff.Root.Get<ResRef>("Field_ResRef", ""));
        }

        [TestMethod]
        public void abc()
        {

            var ini =
                """
                [GFFList]
                Table0=test.gff

                [test.gff]
                AddField1=tl_addStructToExistingList
                locstring(stringref)=321
                locstring(lang1)=helloworld

                [tl_addStructToExistingList]
                FieldType=Struct
                TypeId=123
                Path=L1
                Label=
                AddField0=addFieldToNewStruct

                [addFieldToNewStruct]
                FieldType=ExoLocString
                StrRef=123
                lang1=hello world
                Label=lol
                """;

            var data = new LegacyINIReader(ini).Parse();

            //var modifier = data.GFFFiles.First().Modifiers.First();
            //modifier.Apply(gff, memory, logger);

            data.GFFFiles.First().Modifiers.ForEach(x => x.Apply(gff, memory, logger));

            var x = gff.Root.Fields.ElementAt(1).Value;
        }
    }
}
