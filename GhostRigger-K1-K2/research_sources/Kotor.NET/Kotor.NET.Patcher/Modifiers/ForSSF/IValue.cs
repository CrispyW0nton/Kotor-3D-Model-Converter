using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorSSF;

namespace Kotor.NET.Patcher.Modifiers.ForSSF
{
    public interface IValue
    {
        public int GetValue(IMemory memory, SSF ssf, CreatureSound sound);
    }
}
