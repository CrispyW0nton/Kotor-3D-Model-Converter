// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patching.Diff;
using Kotor.NET.Patching.Modifiers.For2DA;

namespace Kotor.NET.Tests.Tests.Patching.Diff
{
    [TestClass]
    public class TestDiff2DA
    {
        [TestMethod]
        public void IsSame_ColumnCountMismatch()
        {
            var older = new TwoDA();
            older.AddColumn("ABC");
            older.AddColumn("123");

            var newer = new TwoDA();
            newer.AddColumn("ABC");

            var diff = new Diff2DA(older, newer);

            // Columns do not match so the 2DAs are not the same.
            Assert.IsFalse(diff.IsSame());
        }

        [TestMethod]
        public void IsSame_RowCountMismatch()
        {
            var older = new TwoDA();
            older.AddColumn("A");
            older.AddColumn("B");
            older.AddRow("1");
            older.AddRow("2");

            var newer = new TwoDA();
            newer.AddColumn("A");
            newer.AddColumn("B");
            newer.AddRow("1");

            var diff = new Diff2DA(older, newer);

            // One has more rows then the others so the 2DAs are not the same.
            Assert.IsFalse(diff.IsSame());
        }

        [TestMethod]
        public void IsSame_CellMismatch()
        {
            var older = new TwoDA();
            older.AddColumn("A");
            older.AddColumn("B");
            older.AddRow("1");
            older.AddRow("2");

            var newer = new TwoDA();
            newer.AddColumn("A");
            newer.AddColumn("B");
            newer.AddRow("1");
            newer.AddRow("2");
            newer.Row(0).SetCell("A", "asdf");

            var diff = new Diff2DA(older, newer);

            // One has more rows then the others so the 2DAs are not the same.
            Assert.IsFalse(diff.IsSame());
        }

        [TestMethod]
        public void IsSame_AreMatching()
        {
            var older = new TwoDA();
            older.AddColumn("A");
            older.AddColumn("B");
            older.AddRow("1");
            older.AddRow("2");
            older.Row(0).SetCell("A", "asdf");

            var newer = new TwoDA();
            newer.AddColumn("A");
            newer.AddColumn("B");
            newer.AddRow("1");
            newer.AddRow("2");
            newer.Row(0).SetCell("A", "asdf");

            var diff = new Diff2DA(older, newer);

            // One has more rows then the others so the 2DAs are not the same.
            Assert.IsTrue(diff.IsSame());
        }

        [TestMethod]
        public void Find_NewColumn()
        {
            var older = new TwoDA();
            older.AddColumn("A");
            var oRow0 = older.AddRow("0");
            var oRow1 = older.AddRow("1");
            oRow0.SetCell("A", "a0");
            oRow1.SetCell("A", "a1");

            var newer = new TwoDA();
            newer.AddColumn("A");
            newer.AddColumn("B");
            var nRow0 = newer.AddRow("0");
            var nRow1 = newer.AddRow("1");
            nRow0.SetCell("A", "a0");
            nRow1.SetCell("A", "a1");
            nRow0.SetCell("B", "b1");

            var diff = new Diff2DA(older, newer);
            var modifiers = diff.Find();

            // Check that only a single modifier was found
            Assert.AreEqual(1, modifiers.Count);
            // Check that the modifier is to add a column
            Assert.IsInstanceOfType(modifiers[0], typeof(AddColumn2DAModifier));

            // Check that the modifier is accurate
            var modifier = (AddColumn2DAModifier)modifiers[0];
            Assert.AreEqual("B", modifier.ColumnHeader);
            Assert.AreEqual("", modifier.DefaultValue);
            Assert.AreEqual(1, modifier.Values.Count);
        }

        [TestMethod]
        public void Find_NewRow()
        {
            var older = new TwoDA();
            older.AddColumn("A");
            older.AddColumn("B");
            var oRow0 = older.AddRow("0");
            var oRow1 = older.AddRow("1");
            oRow0.SetCell("A", "a0");
            oRow1.SetCell("A", "a1");
            oRow1.SetCell("B", "b1");

            var newer = new TwoDA();
            newer.AddColumn("A");
            newer.AddColumn("B");
            var nRow0 = newer.AddRow("0");
            var nRow1 = newer.AddRow("1");
            var nRow2 = newer.AddRow("2");
            nRow0.SetCell("A", "a0");
            nRow1.SetCell("A", "a1");
            nRow1.SetCell("B", "b1");
            nRow2.SetCell("A", "a2");
            nRow2.SetCell("B", "b2");

            var diff = new Diff2DA(older, newer);

            // Columns do not match so the 2DAs are not the same.
            diff.Find();
        }
    }
}
