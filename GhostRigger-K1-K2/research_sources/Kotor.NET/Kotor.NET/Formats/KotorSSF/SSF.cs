using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;

namespace Kotor.NET.Formats.KotorSSF
{
    public class SSF
    {
        internal Dictionary<CreatureSound, int> _sounds;

        public int BattleCry1 { get => _sounds[CreatureSound.BATTLE_CRY_1]; set => _sounds[CreatureSound.BATTLE_CRY_1] = value; }
        public int BattleCry2 { get => _sounds[CreatureSound.BATTLE_CRY_2]; set => _sounds[CreatureSound.BATTLE_CRY_2] = value; }
        public int BattleCry3 { get => _sounds[CreatureSound.BATTLE_CRY_3]; set => _sounds[CreatureSound.BATTLE_CRY_3] = value; }
        public int BattleCry4 { get => _sounds[CreatureSound.BATTLE_CRY_4]; set => _sounds[CreatureSound.BATTLE_CRY_4] = value; }
        public int BattleCry5 { get => _sounds[CreatureSound.BATTLE_CRY_5]; set => _sounds[CreatureSound.BATTLE_CRY_5] = value; }
        public int BattleCry6 { get => _sounds[CreatureSound.BATTLE_CRY_6]; set => _sounds[CreatureSound.BATTLE_CRY_6] = value; }
        public int Select1 { get => _sounds[CreatureSound.SELECT_1]; set => _sounds[CreatureSound.SELECT_1] = value; }
        public int Select2 { get => _sounds[CreatureSound.SELECT_2]; set => _sounds[CreatureSound.SELECT_2] = value; }
        public int Select3 { get => _sounds[CreatureSound.SELECT_3]; set => _sounds[CreatureSound.SELECT_3] = value; }
        public int AttackGrunt1 { get => _sounds[CreatureSound.ATTACK_GRUNT_1]; set => _sounds[CreatureSound.ATTACK_GRUNT_1] = value; }
        public int AttackGrunt2 { get => _sounds[CreatureSound.ATTACK_GRUNT_2]; set => _sounds[CreatureSound.ATTACK_GRUNT_2] = value; }
        public int AttackGrunt3 { get => _sounds[CreatureSound.ATTACK_GRUNT_3]; set => _sounds[CreatureSound.ATTACK_GRUNT_3] = value; }
        public int PainGrunt1 { get => _sounds[CreatureSound.PAIN_GRUNT_1]; set => _sounds[CreatureSound.PAIN_GRUNT_1] = value; }
        public int PainGrunt2 { get => _sounds[CreatureSound.PAIN_GRUNT_2]; set => _sounds[CreatureSound.PAIN_GRUNT_2] = value; }
        public int LowHealth { get => _sounds[CreatureSound.LOW_HEALTH]; set => _sounds[CreatureSound.LOW_HEALTH] = value; }
        public int Dead { get => _sounds[CreatureSound.DEAD]; set => _sounds[CreatureSound.DEAD] = value; }
        public int CriticalHit { get => _sounds[CreatureSound.CRITICAL_HIT]; set => _sounds[CreatureSound.CRITICAL_HIT] = value; }
        public int TargetImmune { get => _sounds[CreatureSound.TARGET_IMMUNE]; set => _sounds[CreatureSound.TARGET_IMMUNE] = value; }
        public int LayMine { get => _sounds[CreatureSound.LAY_MINE]; set => _sounds[CreatureSound.LAY_MINE] = value; }
        public int DisarmMine { get => _sounds[CreatureSound.DISARM_MINE]; set => _sounds[CreatureSound.DISARM_MINE] = value; }
        public int BeginStealth { get => _sounds[CreatureSound.BEGIN_STEALTH]; set => _sounds[CreatureSound.BEGIN_STEALTH] = value; }
        public int BeginSearch { get => _sounds[CreatureSound.BEGIN_SEARCH]; set => _sounds[CreatureSound.BEGIN_SEARCH] = value; }
        public int BeginUnlock { get => _sounds[CreatureSound.BEGIN_UNLOCK]; set => _sounds[CreatureSound.BEGIN_UNLOCK] = value; }
        public int UnlockFailed { get => _sounds[CreatureSound.UNLOCK_FAILED]; set => _sounds[CreatureSound.UNLOCK_FAILED] = value; }
        public int UnlockSucceeded { get => _sounds[CreatureSound.UNLOCK_SUCCEEDED]; set => _sounds[CreatureSound.UNLOCK_SUCCEEDED] = value; }
        public int SeparatedFromPart { get => _sounds[CreatureSound.SEPARATED_FROM_PARTY]; set => _sounds[CreatureSound.SEPARATED_FROM_PARTY] = value; }
        public int RejoindParty { get => _sounds[CreatureSound.REJOINED_PARTY]; set => _sounds[CreatureSound.REJOINED_PARTY] = value; }
        public int Poisoned { get => _sounds[CreatureSound.POISONED]; set => _sounds[CreatureSound.POISONED] = value; }

        public SSF()
        {
            _sounds = new Dictionary<CreatureSound, int>();
            Reset();
        }

        public void Reset()
        {
            _sounds = new Dictionary<CreatureSound, int>
            {
                [CreatureSound.BATTLE_CRY_1] = new int(),
                [CreatureSound.BATTLE_CRY_2] = new int(),
                [CreatureSound.BATTLE_CRY_3] = new int(),
                [CreatureSound.BATTLE_CRY_4] = new int(),
                [CreatureSound.BATTLE_CRY_5] = new int(),
                [CreatureSound.BATTLE_CRY_6] = new int(),
                [CreatureSound.SELECT_1] = new int(),
                [CreatureSound.SELECT_2] = new int(),
                [CreatureSound.SELECT_3] = new int(),
                [CreatureSound.ATTACK_GRUNT_1] = new int(),
                [CreatureSound.ATTACK_GRUNT_2] = new int(),
                [CreatureSound.ATTACK_GRUNT_3] = new int(),
                [CreatureSound.PAIN_GRUNT_1] = new int(),
                [CreatureSound.PAIN_GRUNT_2] = new int(),
                [CreatureSound.LOW_HEALTH] = new int(),
                [CreatureSound.DEAD] = new int(),
                [CreatureSound.CRITICAL_HIT] = new int(),
                [CreatureSound.TARGET_IMMUNE] = new int(),
                [CreatureSound.LAY_MINE] = new int(),
                [CreatureSound.DISARM_MINE] = new int(),
                [CreatureSound.BEGIN_STEALTH] = new int(),
                [CreatureSound.BEGIN_SEARCH] = new int(),
                [CreatureSound.BEGIN_UNLOCK] = new int(),
                [CreatureSound.UNLOCK_FAILED] = new int(),
                [CreatureSound.UNLOCK_SUCCEEDED] = new int(),
                [CreatureSound.SEPARATED_FROM_PARTY] = new int(),
                [CreatureSound.REJOINED_PARTY] = new int(),
                [CreatureSound.POISONED] = new int(),
            };
        }

        public void Set(CreatureSound sound, int stringref)
        {
            _sounds[sound] = stringref;
        }

        public int Get(CreatureSound sound)
        {
            return _sounds[sound];
        }
    }
}
