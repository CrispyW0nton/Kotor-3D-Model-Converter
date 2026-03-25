using Kotor.NET.Patching;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Patching.Modifiers.For2DA.Values;
using Kotor.NET.Patching.Modifiers.For2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Patching.Modifiers.For2DA.Targets;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Tests.Tests.Patching.Modifiers.For2DA
{
    [TestClass]
    public class TestEditRowModifier
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
        public void EditCells()
        {
            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("b"),
                ["C3"] = new ConstantValue("c"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var target = new RowIndexTarget(1);
            var modifier = new ChangeRow2DAModifier(target, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // No rows were inserted.
            Assert.AreEqual(2, twoda.Rows().Count);
            // The cells have the correct values.
            Assert.AreEqual("a", twoda.Row(1).GetCell("C1"));
            Assert.AreEqual("b", twoda.Row(1).GetCell("C2"));
            Assert.AreEqual("c", twoda.Row(1).GetCell("C3"));
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
            var target = new RowIndexTarget(1);
            var modifier = new ChangeRow2DAModifier(target, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // The correct value was stored into the 2DA Memory.
            Assert.AreEqual("1", memory.From2DAToken(30));
        }
    }
}
