using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Patching.Parsers.LegacyINI;
using Kotor.NET.Patching;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using Moq.AutoMock;
using Kotor.NET.Patching.Modifiers;
using Kotor.NET.Formats.KotorSSF;

namespace Kotor.NET.Tests.Tests.Patching.Parsers.LegacyINI
{
    [TestClass]
    public class TestSSF
    {
        IMemory memory;
        Logger logger;
        SSF ssf;

        [TestInitialize]
        public void Init()
        {
            var mocker = new AutoMocker();

            memory = new Memory();
            logger = new Logger();
            ssf = new SSF();

            memory.Set2DAToken(1, "432");
            memory.SetTLKToken(1, 987);
        }

        [TestMethod]
        public void AssignConstant()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                Battlecry 1=5123
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.SSFFiles.First().Modifiers.First();

            modifier.Apply(ssf, memory, logger);

            // Check that the sound has been assigned the correct StrRef
            Assert.AreEqual(5123, ssf.BattleCry1);
        }

        [TestMethod]
        public void Assign2DAMemory_Exists()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                Battlecry 1=2DAMEMORY1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.SSFFiles.First().Modifiers.First();

            modifier.Apply(ssf, memory, logger);

            // Check that the sound has been assigned the correct StrRef
            Assert.AreEqual(432, ssf.BattleCry1);
        }
        [TestMethod]
        public void Assign2DAMemory_NotExists()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                Battlecry 1=2DAMEMORY2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.SSFFiles.First().Modifiers.First();

            modifier.Apply(ssf, memory, logger);

            // Check that a warning has occured
            Assert.AreEqual(1, logger.Logs.Where(x => x.LogLevel == LogLevel.Warning).Count());
        }

        [TestMethod]
        public void AssignStrRef_Exists()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                Battlecry 1=StrRef1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.SSFFiles.First().Modifiers.First();

            modifier.Apply(ssf, memory, logger);

            // Check that the sound has been assigned the correct StrRef
            Assert.AreEqual(987, ssf.BattleCry1);
        }
        [TestMethod]
        public void AssignStrRef_NotExists()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                Battlecry 1=StrRef2
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.SSFFiles.First().Modifiers.First();

            modifier.Apply(ssf, memory, logger);

            // Check that a warning has occured
            Assert.AreEqual(1, logger.Logs.Where(x => x.LogLevel == LogLevel.Warning).Count());
        }

        [TestMethod]
        public void AllEntriesHaveCorrectKeys()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                Battlecry 1=1
                Battlecry 2=2
                Battlecry 3=3
                Battlecry 4=4
                Battlecry 5=5
                Battlecry 6=6
                Selected 1=7
                Selected 2=8
                Selected 3=9
                Attack 1=10
                Attack 2=11
                Attack 3=12
                Pain 1=13
                Pain 2=14
                Low health=15
                Death=16
                Critical hit=17
                Target immune=18
                Place mine=19
                Disarm mine=20
                Stealth on=21
                Search=22
                Pick lock start=23
                Pick lock fail=24
                Pick lock done=25
                Leave party=26
                Rejoin party=27
                Poisoned=28
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifiers = data.SSFFiles.First().Modifiers;

            modifiers.ForEach(x => x.Apply(ssf, memory, logger));

            // Check that the sound has been assigned the correct StrRef
            Assert.AreEqual(1, ssf.BattleCry1);
            Assert.AreEqual(2, ssf.BattleCry2);
            Assert.AreEqual(3, ssf.BattleCry3);
            Assert.AreEqual(4, ssf.BattleCry4);
            Assert.AreEqual(5, ssf.BattleCry5);
            Assert.AreEqual(6, ssf.BattleCry6);
            Assert.AreEqual(7, ssf.Select1);
            Assert.AreEqual(8, ssf.Select2);
            Assert.AreEqual(9, ssf.Select3);
            Assert.AreEqual(10, ssf.AttackGrunt1);
            Assert.AreEqual(11, ssf.AttackGrunt2);
            Assert.AreEqual(12, ssf.AttackGrunt3);
            Assert.AreEqual(13, ssf.PainGrunt1);
            Assert.AreEqual(14, ssf.PainGrunt2);
            Assert.AreEqual(15, ssf.LowHealth);
            Assert.AreEqual(16, ssf.Dead);
            Assert.AreEqual(17, ssf.CriticalHit);
            Assert.AreEqual(18, ssf.TargetImmune);
            Assert.AreEqual(19, ssf.LayMine);
            Assert.AreEqual(20, ssf.DisarmMine);
            Assert.AreEqual(21, ssf.BeginStealth);
            Assert.AreEqual(22, ssf.BeginSearch);
            Assert.AreEqual(23, ssf.BeginUnlock);
            Assert.AreEqual(24, ssf.UnlockFailed);
            Assert.AreEqual(25, ssf.UnlockSucceeded);
            Assert.AreEqual(26, ssf.SeparatedFromPart);
            Assert.AreEqual(27, ssf.RejoindParty);
            Assert.AreEqual(28, ssf.Poisoned);
        }

        [TestMethod]
        public void CaseInsensitive()
        {
            var ini =
                """
                [SSFList]
                File0=test.ssf

                [test.ssf]
                BatTleCrY 1=1
                """;
            var data = new LegacyINIReader(ini).Parse();
            var modifier = data.SSFFiles.First().Modifiers.First();

            modifier.Apply(ssf, memory, logger);

            // Check that the sound has been assigned
            Assert.AreEqual(1, ssf.BattleCry1);
        }
    }
}
