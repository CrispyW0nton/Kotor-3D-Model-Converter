using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patching;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Patching.Modifiers.For2DA;
using Kotor.NET.Patching.Modifiers.For2DA.Values;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tests.Tests.Patching.Modifiers.For2DA
{
    [TestClass]
    public class TestAddRowModifierModifier
    {
        Memory memory;
        Logger logger;
        TwoDA twoda;

        [TestInitialize]
        public void Init()
        {
            memory = new();
            memory.Set2DAToken(0, "2");
            memory.SetTLKToken(0, 2);

            logger = new();

            twoda = new();
            twoda.AddColumn("C1");
            twoda.AddColumn("C2");
            twoda.AddColumn("C3");
            twoda.AddRow("l0");
            twoda.AddRow("l1");
        }

        [TestMethod]
        public void NotExclusive_NoRowLabel_NoStore()
        {
            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("b"),
                ["C3"] = new ConstantValue("c"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var modifier = new AddRow2DAModifier(null, null, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // A new row was inserted. 
            Assert.AreEqual(3, twoda.Rows().Count);
            // The row header was assigned the row index as a string.
            Assert.AreEqual("2", twoda.Row(2).Header);
            // The cells have the correct values.
            Assert.AreEqual("a", twoda.Row(2).GetCell("C1"));
            Assert.AreEqual("b", twoda.Row(2).GetCell("C2"));
            Assert.AreEqual("c", twoda.Row(2).GetCell("C3"));
        }

        [TestMethod]
        public void AssignRowLabel()
        {
            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("b"),
                ["C3"] = new ConstantValue("c"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var rowLabel = new ConstantValue("somelabel");
            var modifier = new AddRow2DAModifier(null, rowLabel, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // A new row was inserted. 
            Assert.AreEqual(3, twoda.Rows().Count);
            // The row header was assigned the value stored in the modifier instance.
            Assert.AreEqual("somelabel", twoda.Row(2).Header);
            // The cells have the correct values.
            Assert.AreEqual("a", twoda.Row(2).GetCell("C1"));
            Assert.AreEqual("b", twoda.Row(2).GetCell("C2"));
            Assert.AreEqual("c", twoda.Row(2).GetCell("C3"));
        }

        [TestMethod]
        public void ExclusiveAndExisting()
        {
            twoda.Rows()[0].SetCell("C1", "a");

            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("b"),
                ["C3"] = new ConstantValue("c"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var modifier = new AddRow2DAModifier("C1", null, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // No new rows were added.
            Assert.AreEqual(2, twoda.Rows().Count);
            // The cells were updated to have the correct values.
            Assert.AreEqual("a", twoda.Rows()[0].GetCell("C1"));
            Assert.AreEqual("b", twoda.Rows()[0].GetCell("C2"));
            Assert.AreEqual("c", twoda.Rows()[0].GetCell("C3"));
        }

        [TestMethod]
        public void ExclusiveAndNotExisting()
        {
            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("b"),
                ["C3"] = new ConstantValue("c"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var modifier = new AddRow2DAModifier("C1", null, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // A new row was inserted.
            Assert.AreEqual(3, twoda.Rows().Count);
            // The cells have the correct values.
            Assert.AreEqual("a", twoda.Rows()[2].GetCell("C1"));
            Assert.AreEqual("b", twoda.Rows()[2].GetCell("C2"));
            Assert.AreEqual("c", twoda.Rows()[2].GetCell("C3"));
        }

        [TestMethod]
        public void StoreValue()
        {
            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("b"),
                ["C3"] = new ConstantValue("c"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>
            {
                [30] = new RowIndexValue(),
            };
            var modifier = new AddRow2DAModifier(null, null, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // The correct value was stored into the 2DA Memory.
            Assert.AreEqual("2", memory.From2DAToken(30));
        }
    }
}
