using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Patcher.Modifiers.ForGFF
{
    public interface IGFFModifier : IModifier<GFF>
    {
        void SetNavigator(GFFNavigator navigator);
    }
}
