using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Creature
{
    public class Class
    {
        public int ClassID { get; set; }
        public int ClassLevel { get; set; }
        public List<ForcePower> ForcePowers { get; set; }
    }
}
