using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patching;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Patching.Modifiers.For2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tests.Tests.Patching.Modifiers.For2DA
{
    [TestClass]
    public class TestAddColumnModifier
    {
        Memory? memory;
        Logger? logger;
        TwoDA? twoda;

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
        public void CorrectColumnHeader()
        {
            var modifier = new AddColumn2DAModifier("NewColumn", "", new(), new());

            modifier.Apply(twoda, memory, logger);

            // A new column was inserted.
            Assert.AreEqual(4, twoda.ColumnHeaders().Count);
            // The correct header was applied.
            Assert.AreEqual("NewColumn", twoda.ColumnHeaders().Last());
        }

        [TestMethod]
        public void CorrectDefaultValue()
        {
            var modifier = new AddColumn2DAModifier("NewColumn", "xyz", new(), new());

            modifier.Apply(twoda, memory, logger);

            // The cells under the new column have the correct value.
            Assert.AreEqual("xyz", twoda.Row(0).GetCell("NewColumn"));
            Assert.AreEqual("xyz", twoda.Row(1).GetCell("NewColumn"));
        }
    }
}
