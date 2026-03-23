using Kotor.NET.Patching.Modifiers.For2DA.Targets;
using Kotor.NET.Patching;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Patching.Modifiers.For2DA.Values;
using Kotor.NET.Patching.Modifiers.For2DA;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Formats.Kotor2DA;

namespace Kotor.NET.Tests.Tests.Patching.Modifiers.For2DA
{
    [TestClass]
    public class TestCopyRowModifier
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
        public void CopyRow()
        {
            var target = new RowIndexTarget(1);
            var data = new Dictionary<string, IValue>
            {
                ["C1"] = new ConstantValue("a"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var modifier = new CopyRow2DAModifier(target, null, null, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // A new row was inserted. 
            Assert.AreEqual(3, twoda.Rows().Count);
            // The row header was assigned the value of the row index.
            Assert.AreEqual("2", twoda.Row(2).Header);
            // The cells have the correct values.
            Assert.AreEqual("a", twoda.Row(2).GetCell("C1"));
            Assert.AreEqual("", twoda.Row(2).GetCell("C2"));
            Assert.AreEqual("", twoda.Row(2).GetCell("C3"));
        }

        [TestMethod]
        public void CopyRow_ExclusiveAndExisting()
        {
            twoda.Row(0).SetCell("C1", "a");

            twoda.Row(1).SetCell("C2", "x");
            twoda.Row(1).SetCell("C3", "y");

            var target = new RowIndexTarget(1);
            var data = new Dictionary<string, IValue>()
            {
                ["C1"] = new ConstantValue("a"),
                ["C2"] = new ConstantValue("00"),
            };
            var toStoreInMemory = new Dictionary<int, IValue>();
            var modifier = new CopyRow2DAModifier(target, "C1", null, data, toStoreInMemory);

            modifier.Apply(twoda, memory, logger);

            // No new rows were added.
            Assert.AreEqual(2, twoda.Rows().Count);
            // The row header was unaltered.
            Assert.AreEqual("l0", twoda.Rows()[0].Header);
            // The specified cells were updated to have the correct values.
            Assert.AreEqual("a", twoda.Rows()[0].GetCell("C1"));
            Assert.AreEqual("00", twoda.Rows()[0].GetCell("C2"));
            // The unspecified cell retains its original value.
            Assert.AreEqual("y", twoda.Rows()[0].GetCell("C3"));
        }
    }
}
