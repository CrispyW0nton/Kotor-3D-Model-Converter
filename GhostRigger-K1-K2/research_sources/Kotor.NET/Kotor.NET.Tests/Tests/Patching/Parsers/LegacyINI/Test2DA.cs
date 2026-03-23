using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patching;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Patching.Modifiers.For2DA;
using Kotor.NET.Patching.Modifiers.For2DA.Targets;
using Kotor.NET.Patching.Parsers.LegacyINI;
using Moq.AutoMock;

namespace Kotor.NET.Tests.Tests.Patching.Parsers.LegacyINI
{
    [TestClass]
    public class Test2DA
    {
        IMemory memory;
        Logger logger;
        TwoDA twoda;

        [TestInitialize]
        public void Init()
        {
            var mocker = new AutoMocker();

            memory = new Memory();
            logger = new Logger();
            twoda = new TwoDA();

            twoda.AddColumn("ColumnA");
            twoda.AddColumn("ColumnB");
            twoda.AddColumn("ColumnC");

            var row0 = twoda.AddRow("0");
            row0.SetCell("ColumnA", "0a");
            row0.SetCell("ColumnB", "0b");
            row0.SetCell("ColumnC", "0c");

            var row1 = twoda.AddRow("1");
            row1.SetCell("ColumnA", "1a");
            row1.SetCell("ColumnB", "1b");
            row1.SetCell("ColumnC", "1c");

            var row2 = twoda.AddRow("2");
            row2.SetCell("ColumnA", "2a");
            row2.SetCell("ColumnB", "2b");
            row2.SetCell("ColumnC", "2c");

            memory.Set2DAToken(0, "X");
            memory.Set2DAToken(3, "Y");

            memory.SetTLKToken(1, 111);
            memory.SetTLKToken(3, 333);
        }


        #region Add Column
        [TestMethod]
        public void AddColumn_OnlyHeaderSpecified()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the default value defaults to blank when not specified
            Assert.AreEqual("", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("", twoda.Row(2)!.GetCell("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_DefaultValueSpecified()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                DefaultValue=abc
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the default value is applied correctly in the new column
            Assert.AreEqual("abc", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("abc", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("abc", twoda.Row(2)!.GetCell("ColumnD"));
        }

        //

        [TestMethod]
        public void AddColumn_TargetRowHeader_AssignConstantValue_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                L0=a
                L1=b
                L2=c
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("a", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("b", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("c", twoda.Row(2)!.GetCell("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_TargetRowHeader_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                L3=a
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_TargetRowIndex_AssignFromConstantValue_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I0=a
                I1=b
                I2=c
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("a", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("b", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("c", twoda.Row(2)!.GetCell("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_TargetRowIndex_AssignFrom2DAMemoryValue_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I0=2DAMEMORY0
                I1=2DAMEMORY3
                I2=2DAMEMORY0
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("X", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("Y", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("X", twoda.Row(2)!.GetCell("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_TargetRowIndex_AssignFromTLKMemoryValue_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I0=StrRef1
                I1=StrRef3
                I2=StrRef1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("111", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("333", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("111", twoda.Row(2)!.GetCell("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_TargetRowIndex_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I0=StrRef9
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
        }

        //

        [TestMethod]
        public void AddColumn_Assign2DAMemoryFromRowLabel_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                L2=abc
                2DAMEMORY9=L2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("abc", twoda.Row(2)!.GetCell("ColumnD"));
            // Check that 2DAMEMOMRY has stored the correct value
            Assert.AreEqual("abc", memory.From2DAToken(9));
        }

        [TestMethod]
        public void AddColumn_Assign2DAMemoryFromRowLabel_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                L2=abc
                2DAMEMORY9=L2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("abc", twoda.Row(2)!.GetCell("ColumnD"));
            // Check that 2DAMEMOMRY has stored the correct value
            Assert.AreEqual("abc", memory.From2DAToken(9));
        }

        [TestMethod]
        public void AddColumn_Assign2DAMemoryFromRowIndex_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I2=abc
                2DAMEMORY9=I2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
            // Check the values are assigned correctly to each row
            Assert.AreEqual("", twoda.Row(0)!.GetCell("ColumnD"));
            Assert.AreEqual("", twoda.Row(1)!.GetCell("ColumnD"));
            Assert.AreEqual("abc", twoda.Row(2)!.GetCell("ColumnD"));
            // Check that 2DAMEMOMRY has stored the correct value
            Assert.AreEqual("abc", memory.From2DAToken(9));
        }

        [TestMethod]
        public void AddColumn_Assign2DAMemoryFromRowIndex_TokenAvailable_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I2=abc
                2DAMEMORY9=I3
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
        }

        [TestMethod]
        public void AddColumn_Assign2DAMemoryFromRowIndex_TokenTaken_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddColumn0=addcolumn0

                [addcolumn0]
                ColumnLabel=ColumnD
                I2=abc
                2DAMEMORY3=I2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an warning has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Warning));
            // Check the column count has increased by 1
            Assert.AreEqual(4, twoda.ColumnHeaders().Count());
            // Check that the list of column headers are as expected
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnA"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnB"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnC"));
            Assert.IsTrue(twoda.ColumnHeaders().Contains("ColumnD"));
        }
        #endregion

        #region Change Row
        [TestMethod]
        public void ChangeRow_TargetRowLabel_Found()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowLabel=2
                ColumnA=X 
                ColumnB=Y
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("X", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("Y", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void ChangeRow_TargetRowLabel_NotFound()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowLabel=31
                ColumnA=X 
                ColumnB=Y
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void ChangeRow_TargetRowIndex_Found()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=2
                ColumnA=X 
                ColumnB=Y
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("X", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("Y", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void ChangeRow_TargetRowIndex_NotFound()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=31
                ColumnA=X 
                ColumnB=Y
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void ChangeRow_TargetLabelIndex_Found()
        {
            twoda.AddColumn("label");
            twoda.Row(0).SetCell("label", "l0");
            twoda.Row(1).SetCell("label", "l1");
            twoda.Row(2).SetCell("label", "l2");
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                LabelIndex=l2
                ColumnA=X 
                ColumnB=Y
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("l0", twoda.Row("0")!.GetCell("label"));
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("l1", twoda.Row("1")!.GetCell("label"));
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("l2", twoda.Row("2")!.GetCell("label"));
            Assert.AreEqual("X", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("Y", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void ChangeRow_TargetLabelIndex_NotFound()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                LabelIndex=31
                ColumnA=X 
                ColumnB=Y
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }

        //

        [TestMethod]
        public void ChangeRow_AssignValueAs2DAMemory_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                ColumnA=2DAMEMORY0
                ColumnB=2DAMEMORY3
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("X", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("Y", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void ChangeRow_AssignValueAs2DAMemory_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                ColumnA=2DAMEMORY1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void ChangeRow_AssignValueAsTLKMemory_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                ColumnA=StrRef1
                ColumnB=StrRef3
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("111", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("333", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void ChangeRow_AssignValueAsTLKMemory_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                ColumnA=StrRef0
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }

        //

        [TestMethod]
        public void ChangeRow_Assign2DAMemoryFromColumn_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                2DAMEMORY5=ColumnA
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check memory saved correctly
            Assert.AreEqual("0a", memory.From2DAToken(5));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void ChangeRow_Assign2DAMemoryFromColumn_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                2DAMEMORY5=dfggdfdfg
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row("0")!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row("0")!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row("0")!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row("1")!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row("1")!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row("1")!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row("2")!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row("2")!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row("2")!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void ChangeRow_Assign2DAMemoryFromRowIndex()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                2DAMEMORY5=RowIndex
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check memory saved correctly
            Assert.AreEqual("0", memory.From2DAToken(5));
            // Check that no warnings occured
            Assert.AreEqual(0, logger.Logs.Count(x => x.LogLevel == LogLevel.Warning));
        }

        [TestMethod]
        public void ChangeRow_Assign2DAMemoryFromRowLabel()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                ChangeRow0=changerow

                [changerow]
                RowIndex=0
                2DAMEMORY5=RowLabel
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check memory saved correctly
            Assert.AreEqual("0", memory.From2DAToken(5));
            // Check that no warnings occured
            Assert.AreEqual(0, logger.Logs.Count(x => x.LogLevel == LogLevel.Warning));
        }

        #endregion

        #region Add Row
        [TestMethod]
        public void AddRow_ConstantValues()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ColumnA=3a 
                ColumnB=3b
                ColumnC=3c
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("3a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("3b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("3c", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void AddRow_2DAMemoryValues()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ColumnA=2DAMEMORY0
                ColumnB=2DAMEMORY3
                ColumnC=2DAMEMORY0
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("X", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("Y", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("X", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void AddRow_TLKMemoryValues()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ColumnA=StrRef1 
                ColumnB=StrRef3
                ColumnC=StrRef1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("111", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("333", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("111", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void AddRow_DefaultValues()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void AddRow_HighestPlusOneValue()
        {
            twoda.AddColumn("ColumnD");
            twoda.Row(0)!.SetCell("ColumnD", "1");
            twoda.Row(1)!.SetCell("ColumnD", "3");
            twoda.Row(2)!.SetCell("ColumnD", "5");

            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ColumnD=high()
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("", twoda.Row(3)!.GetCell("ColumnC"));
            Assert.AreEqual("6", twoda.Row(3)!.GetCell("ColumnD"));
        }

        //

        [TestMethod]
        public void AddRow_RowHeaderAssigned()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                RowLabel=3xyz
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been incremented
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct row label
            Assert.AreEqual("3xyz", twoda.Row(3)!.Header);
        }
        [TestMethod]
        public void AddRow_RowHeaderNotAssigned()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been incremented
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct row label
            Assert.AreEqual("3", twoda.Row(3)!.Header);
        }

        //

        [TestMethod]
        public void AddRow_ExclusiveRowNotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ExclusiveColumn=ColumnA
                ColumnA=3a 
                ColumnB=3b
                ColumnC=3c
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been incremented
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("3a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("3b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("3c", twoda.Row(3)!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void AddRow_ExclusiveRowExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ExclusiveColumn=ColumnA
                ColumnA=2a
                ColumnC=xyz
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check that the third row has been updated
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("xyz", twoda.Row(2)!.GetCell("ColumnC"));
        }

        //

        [TestMethod]
        public void AddRow_Assign2DAMemoryFromColumn_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ColumnA=3a
                ColumnB=3b
                ColumnC=3c
                2DAMEMORY5=ColumnA
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check memory saved correctly
            Assert.AreEqual("3a", memory.From2DAToken(5));
            // Check that an error has not occured
            Assert.AreEqual(0, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count was incremented
            Assert.AreEqual(4, twoda.Rows().Count());
        }
        [TestMethod]
        public void AddRow_Assign2DAMemoryFromColumn_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ColumnA=3a
                ColumnB=3b
                ColumnC=3c
                2DAMEMORY5=dfggdfdfg
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count incremented
            Assert.AreEqual(4, twoda.Rows().Count());
        }

        [TestMethod]
        public void AddRow_Assign2DAMemoryFromRowIndex_ExistingRow()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ExclusiveColumn=ColumnA
                ColumnA=1a
                2DAMEMORY9=RowIndex
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that the memory saved the correct value
            Assert.AreEqual("1", memory.From2DAToken(9));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check that the third row has been updated
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void AddRow_Assign2DAMemoryFromRowIndex_NewRow()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                2DAMEMORY9=RowIndex
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that the memory saved the correct value
            Assert.AreEqual("3", memory.From2DAToken(9));
            // Check the row count was incremented
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check that the third row has been updated
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void AddRow_Assign2DAMemoryFromRowHeader_ExistingRow()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                ExclusiveColumn=ColumnA
                ColumnA=1a
                2DAMEMORY9=RowLabel
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that the memory saved the correct value
            Assert.AreEqual("1", memory.From2DAToken(9));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
        }
        [TestMethod]
        public void AddRow_Assign2DAMemoryFromRowHeader_NewRow()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                AddRow0=addrow

                [addrow]
                RowLabel=row3
                2DAMEMORY9=RowLabel
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that the memory saved the correct value
            Assert.AreEqual("row3", memory.From2DAToken(9));
            // Check the row count was incremented
            Assert.AreEqual(4, twoda.Rows().Count());
        }
        #endregion

        #region Copy Row
        [TestMethod]
        public void CopyRow_TargetRowIndex_Found()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("2a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(3)!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void CopyRow_TargetRowIndex_NotFound()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2123123
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
        }

        [TestMethod]
        public void CopyRow_TargetRowHeader_Found()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowLabel=2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("2a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(3)!.GetCell("ColumnC"));
        }
        [TestMethod]
        public void CopyRow_TargetRowHeader_NotFound()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowLabel=76123
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
            // Check the row count remains the same
            Assert.AreEqual(3, twoda.Rows().Count());
        }

        //

        [TestMethod]
        public void CopyRow_RowHeaderIsAssigned()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                NewRowLabel=row5
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("2a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(3)!.GetCell("ColumnC"));
            // Check the new row has the correct row label
            Assert.AreEqual("row5", twoda.Row(3)!.Header);
        }

        [TestMethod]
        public void CopyRow_RowHeaderIsNotAssigned()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
        }

        //

        [TestMethod]
        public void CopyRow_AssignValueAsConstant()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                ColumnA=3a
                ColumnB=3b
                ColumnC=3c
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("3a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("3b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("3c", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void CopyRow_AssignValueAs2DAMemory_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                ColumnA=2DAMEMORY0
                ColumnB=2DAMEMORY3
                ColumnC=2DAMEMORY0
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("X", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("Y", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("X", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void CopyRow_AssignValueAsTLKMemory_Exists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                ColumnA=StrRef1
                ColumnB=StrRef3
                ColumnC=StrRef1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("111", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("333", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("111", twoda.Row(3)!.GetCell("ColumnC"));
        }

        [TestMethod]
        public void CopyRow_AssignValueAsHigh()
        {
            twoda.AddColumn("ColumnD");
            twoda.Row(0)!.SetCell("ColumnD", "1");
            twoda.Row(1)!.SetCell("ColumnD", "3");
            twoda.Row(2)!.SetCell("ColumnD", "5");

            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=addrow

                [addrow]
                RowIndex=2
                ColumnD=high()
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check the row count has been changed
            Assert.AreEqual(4, twoda.Rows().Count());
            // Check the first row
            Assert.AreEqual("0a", twoda.Row(0)!.GetCell("ColumnA"));
            Assert.AreEqual("0b", twoda.Row(0)!.GetCell("ColumnB"));
            Assert.AreEqual("0c", twoda.Row(0)!.GetCell("ColumnC"));
            // Check the second row
            Assert.AreEqual("1a", twoda.Row(1)!.GetCell("ColumnA"));
            Assert.AreEqual("1b", twoda.Row(1)!.GetCell("ColumnB"));
            Assert.AreEqual("1c", twoda.Row(1)!.GetCell("ColumnC"));
            // Check the third row
            Assert.AreEqual("2a", twoda.Row(2)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(2)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(2)!.GetCell("ColumnC"));
            // Check the new (fourth) row has correct cell values
            Assert.AreEqual("2a", twoda.Row(3)!.GetCell("ColumnA"));
            Assert.AreEqual("2b", twoda.Row(3)!.GetCell("ColumnB"));
            Assert.AreEqual("2c", twoda.Row(3)!.GetCell("ColumnC"));
            Assert.AreEqual("6", twoda.Row(3)!.GetCell("ColumnD"));
        }

        //

        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromColumn_NotExists()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                2DAMEMORY9=fdgdfghj
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that an error has occured
            Assert.AreEqual(1, logger.Logs.Count(x => x.LogLevel == LogLevel.Error));
        }
        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromColumn_Exists_TokenAvailable()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                NewRowLabel=abc
                2DAMEMORY9=ColumnA
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check 2DAMemory at correct token was updated
            Assert.AreEqual("1a", memory.From2DAToken(9));
        }
        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromColumn_Exists_TokenTaken()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                NewRowLabel=abc
                2DAMEMORY0=ColumnA
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that a warning was made
            Assert.AreEqual(1, logger.Logs.Where(x => x.LogLevel == LogLevel.Warning).Count());
            // Check 2DAMemory at correct token was updated
            Assert.AreEqual("1a", memory.From2DAToken(0));
        }


        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromRowLabel_TokenAvailable()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                NewRowLabel=abc
                2DAMEMORY9=RowLabel
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check 2DAMemory at correct token was updated
            Assert.AreEqual("abc", memory.From2DAToken(9));
        }
        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromRowLabel_TokenTaken()
        {
            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                NewRowLabel=abc
                2DAMEMORY0=RowLabel
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that a warning was made
            Assert.AreEqual(1, logger.Logs.Where(x => x.LogLevel == LogLevel.Warning).Count());
            // Check 2DAMemory at correct token was updated
            Assert.AreEqual("abc", memory.From2DAToken(0));
        }


        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromRowIndex_TokenAvailable()
        {
            twoda.AddColumn("ColumnD");
            twoda.Row(0)!.SetCell("ColumnD", "1");
            twoda.Row(1)!.SetCell("ColumnD", "3");
            twoda.Row(2)!.SetCell("ColumnD", "5");

            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                2DAMEMORY9=RowIndex
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check 2DAMemory at correct token was updated
            Assert.AreEqual("3", memory.From2DAToken(9));
        }
        [TestMethod]
        public void CopyRow_Assign2DAMemoryFromRowIndex_TokenTaken()
        {
            twoda.AddColumn("ColumnD");
            twoda.Row(0)!.SetCell("ColumnD", "1");
            twoda.Row(1)!.SetCell("ColumnD", "3");
            twoda.Row(2)!.SetCell("ColumnD", "5");

            var ini =
                """
                [2DAList]
                Table0=test.2da

                [test.2da]
                CopyRow0=copyrow

                [copyrow]
                RowIndex=1
                2DAMEMORY0=RowIndex
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.TwoDAFiles.First().Modifiers.First();

            modifier.Apply(twoda, memory, logger);

            // Check that a warning was made
            Assert.AreEqual(1, logger.Logs.Where(x => x.LogLevel == LogLevel.Warning).Count());
            // Check 2DAMemory at correct token was updated
            Assert.AreEqual("3", memory.From2DAToken(0));
        }
        #endregion
    }
}
